import pandas as pd
from typing import Optional
from modules.db.core import  execute_one, read_df
from datetime import datetime, timezone 

def add_transaction(
    hisse: str, 
    tarih, 
    islem_tipi: str, 
    lot: int, 
    fiyat: float, 
    notu: str = "",
    rsi: Optional[float] = None, # YENİ
    vfi: Optional[float] = None  # YENİ
) -> int:
    """
    Veritabanına yeni bir alım/satım işlemi ekler (RSI ve VFI dahil).
    """
    # SQL sorgusuna yeni sütunları ekliyoruz.
    sql = """
        INSERT INTO transactions (hisse, tarih, islem_tipi, lot, fiyat, notu, rsi, vfi)
        VALUES (:hisse, :tarih, :islem_tipi, :lot, :fiyat, :notu, :rsi, :vfi)
    """
    
    safe_notu = notu if notu is not None else ""
    
    # Parametreler sözlüğüne yeni değerleri ekliyoruz.
    params = {
        "hisse": hisse.upper().strip(),
        "tarih": tarih,
        "islem_tipi": islem_tipi,
        "lot": int(lot),
        "fiyat": float(fiyat),
        "notu": safe_notu,
        "rsi": rsi,
        "vfi": vfi
    }

    return execute_one(sql, params)

def delete_transaction_by_id(transaction_id: int) -> int:
    """
    Verilen ID'ye sahip işlemi FİZİKSEL OLARAK SİLMEZ.
    Bunun yerine `deleted_at` alanını mevcut zamanla günceller.
    """
    # DELETE yerine UPDATE kullanıyoruz.
    sql = "UPDATE transactions SET deleted_at = :now WHERE id = :id AND deleted_at IS NULL"
    params = {
        "id": transaction_id,
        "now": datetime.now(timezone.utc) # Zaman dilimi bilgisiyle (UTC) kayıt
    }
    return execute_one(sql, params)

def load_all_transactions_df() -> pd.DataFrame:
    """
    Tüm işlem geçmişini DataFrame olarak yükler.
    """
    try:
        df = read_df("SELECT * FROM transactions WHERE deleted_at IS NULL ORDER BY tarih DESC, id DESC")
        # Tarih sütunlarını doğru tipe çevirelim
        df['tarih'] = pd.to_datetime(df['tarih']).dt.date
        return df
    except Exception:
        # Tablo yoksa veya hata olursa boş DataFrame döndürür.
        return pd.DataFrame()

def get_current_portfolio_df() -> pd.DataFrame:
    """
    Tüm işlemler üzerinden mevcut açık pozisyonları ve maliyetleri hesaplar.
    Burası yeni modelin kalbidir.
    """
    transactions_df = load_all_transactions_df()
    if transactions_df.empty:
        return pd.DataFrame(columns=["hisse", "lot", "ortalama_maliyet", "toplam_maliyet"])

    # Alış ve Satışları ayır
    alislar = transactions_df[transactions_df['islem_tipi'] == 'ALIŞ'].copy()
    satislar = transactions_df[transactions_df['islem_tipi'] == 'SATIŞ'].copy()

    if alislar.empty:
        return pd.DataFrame(columns=["hisse", "lot", "ortalama_maliyet", "toplam_maliyet"])

    # Ağırlıklı ortalama maliyeti hesapla
    alislar['toplam_tutar'] = alislar['lot'] * alislar['fiyat']
    maliyet_summary = alislar.groupby('hisse').agg(
        toplam_lot_alis=('lot', 'sum'),
        toplam_tutar_alis=('toplam_tutar', 'sum')
    ).reset_index()
    maliyet_summary['ortalama_maliyet'] = maliyet_summary['toplam_tutar_alis'] / maliyet_summary['toplam_lot_alis']
    
    # Satışları hesapla
    satis_summary = satislar.groupby('hisse').agg(
        toplam_lot_satis=('lot', 'sum')
    ).reset_index()

    # İki tabloyu birleştir
    portfolio = pd.merge(maliyet_summary, satis_summary, on='hisse', how='left')
    portfolio['toplam_lot_satis'] = portfolio['toplam_lot_satis'].fillna(0) # Satışı olmayan hisseler için NaN'ı 0 yap

    # Mevcut lot sayısını hesapla
    portfolio['lot'] = portfolio['toplam_lot_alis'] - portfolio['toplam_lot_satis']
    
    # Sadece eldeki pozisyonları göster (lot > 0)
    portfolio = portfolio[portfolio['lot'] > 0].copy()

    if portfolio.empty:
        return pd.DataFrame(columns=["hisse", "lot", "ortalama_maliyet", "toplam_maliyet"])
        
    # Toplam maliyeti hesapla ve gereksiz sütunları at
    portfolio['toplam_maliyet'] = portfolio['lot'] * portfolio['ortalama_maliyet']
    
    final_cols = ["hisse", "lot", "ortalama_maliyet", "toplam_maliyet"]
    portfolio = portfolio[final_cols].sort_values("toplam_maliyet", ascending=False)

    return portfolio


def get_closed_positions_summary() -> pd.DataFrame:
    """
    Kapanmış (tamamı satılmış) pozisyonların özetini hesaplar.
    Her hisse için toplam alım ve satım maliyet/değerlerini döndürür.
    """
    
    df = load_all_transactions_df()
    if df.empty:
        return pd.DataFrame()

    # Alım ve Satım işlemlerini ayır
    alislar = df[df['islem_tipi'] == 'ALIŞ'].copy()
    satislar = df[df['islem_tipi'] == 'SATIŞ'].copy()

    # Hisse bazında alım ve satım lotlarını topla
    alis_summary = alislar.groupby('hisse').agg(
        toplam_lot_alis=('lot', 'sum'),
        ilk_alis_tarihi=('tarih', 'min')
    ).reset_index()

    satis_summary = satislar.groupby('hisse').agg(
        toplam_lot_satis=('lot', 'sum'),
        son_satis_tarihi=('tarih', 'max')
    ).reset_index()

    # Sadece lot sayıları eşit olanları (yani tamamen kapanmış pozisyonları) bul
    closed = pd.merge(
        alis_summary, 
        satis_summary, 
        on='hisse', 
        how='inner', # Sadece her iki df'te de olan hisseler
        suffixes=('_alis', '_satis')
    )
    closed = closed[closed['toplam_lot_alis'] == closed['toplam_lot_satis']]

    if closed.empty:
        return pd.DataFrame()

    # Şimdi bu kapanmış hisseler için maliyet ve satış tutarlarını hesapla
    closed_hisseler = closed['hisse'].unique()
    
    alislar['tutar'] = alislar['lot'] * alislar['fiyat']
    satislar['tutar'] = satislar['lot'] * satislar['fiyat']

    final_summary = []
    for hisse in closed_hisseler:
        hisse_alislar = alislar[alislar['hisse'] == hisse]
        hisse_satislar = satislar[satislar['hisse'] == hisse]
        
        toplam_maliyet = hisse_alislar['tutar'].sum()
        toplam_satis_tutari = hisse_satislar['tutar'].sum()
        
        ilk_alis = hisse_alislar['tarih'].min()
        son_satis = hisse_satislar['tarih'].max()
        
        final_summary.append({
            "hisse": hisse,
            "toplam_maliyet": toplam_maliyet,
            "toplam_satis_tutari": toplam_satis_tutari,
            "ilk_alis_tarihi": ilk_alis,
            "son_satis_tarihi": son_satis,
        })

    return pd.DataFrame(final_summary)