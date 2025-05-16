CREATE TABLE IF NOT EXISTS radar_scores (
    sirket          TEXT    PRIMARY KEY,
    f_skor          INTEGER,
    m_skor          NUMERIC,
    graham_skor     INTEGER,
    lynch_skor      INTEGER,
    intrinsic       NUMERIC,          -- şirket toplam içsel değer
    intrinsic_ps    NUMERIC,          -- hisse başına içsel değer
    cur_price       NUMERIC,          -- güncel fiyat
    mos             NUMERIC,          -- margin‑of‑safety (0‑1 arası)
    premium         NUMERIC,          -- (intrinsic_ps – cur_price) / cur_price
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- performance_log tablosu
CREATE TABLE IF NOT EXISTS performance_log (
    id     SERIAL PRIMARY KEY,
    tarih  DATE        NOT NULL,
    hisse  VARCHAR(20) NOT NULL,
    lot    INTEGER     NOT NULL,
    fiyat  NUMERIC(12,2),

    CONSTRAINT uq_perflog UNIQUE (tarih, hisse)   -- aynı gün–hisse çifti tek olsun
);



-- portfolio.sql
CREATE TABLE IF NOT EXISTS portfolio (
    id            SERIAL PRIMARY KEY,
    hisse         VARCHAR(20)  NOT NULL,
    is_fund       BOOLEAN      NOT NULL DEFAULT FALSE,   -- “Yatırım Fonu mu”
    lot           INTEGER      NOT NULL,
    maliyet       NUMERIC(14,4),
    alis_tarihi   DATE,
    satis_tarihi  DATE,
    satis_fiyat   NUMERIC(14,4),
    notu          TEXT,

    CONSTRAINT uq_portfolio UNIQUE (hisse, alis_tarihi)  -- aynı pozisyon tek olsun
);
