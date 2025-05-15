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