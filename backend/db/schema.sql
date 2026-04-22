-- EXTENSIONS not available in Azure PostgreSQL

-- TABLE 1: admins
CREATE TABLE IF NOT EXISTS admins (
    admin_id      VARCHAR(10)  PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT         NOT NULL,
    role          VARCHAR(30)  NOT NULL DEFAULT 'advisor',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- TABLE 2: customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id   VARCHAR(10)  PRIMARY KEY,
    first_name    VARCHAR(60)  NOT NULL,
    last_name     VARCHAR(60)  NOT NULL,
    email         VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT         NOT NULL,
    risk_profile  VARCHAR(20)  NOT NULL
                  CHECK (risk_profile IN ('conservative','moderate','aggressive')),
    advisor_tier  VARCHAR(20)  NOT NULL
                  CHECK (advisor_tier IN ('standard','premium','elite')),
    joined_date   DATE         NOT NULL DEFAULT CURRENT_DATE,
    last_login    TIMESTAMPTZ,
    country       CHAR(2)      NOT NULL DEFAULT 'US',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- TABLE 3: market_prices
CREATE TABLE IF NOT EXISTS market_prices (
    ticker                VARCHAR(10)   PRIMARY KEY,
    asset_type            VARCHAR(10)   NOT NULL
                          CHECK (asset_type IN ('stock','etf','crypto')),
    price_usd             NUMERIC(18,4) NOT NULL,
    open_price            NUMERIC(18,4),
    change_1d_pct         NUMERIC(8,2),
    volume_24h            VARCHAR(20),
    market_cap            VARCHAR(20),
    predicted_5d_pct      NUMERIC(6,2),
    prediction_confidence INTEGER,
    price_timestamp       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    last_updated          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- TABLE 4: portfolio_holdings
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    holding_id        VARCHAR(12)   PRIMARY KEY,
    customer_id       VARCHAR(10)   NOT NULL
                      REFERENCES customers(customer_id),
    ticker            VARCHAR(10)   NOT NULL,
    asset_type        VARCHAR(10)   NOT NULL
                      CHECK (asset_type IN ('stock','etf','crypto','cash')),
    quantity          NUMERIC(18,6) NOT NULL DEFAULT 0,
    avg_buy_price     NUMERIC(18,4) NOT NULL DEFAULT 0,
    current_price     NUMERIC(18,4) NOT NULL DEFAULT 0,
    unrealized_pl     NUMERIC(18,2) NOT NULL DEFAULT 0,
    unrealized_pl_pct NUMERIC(8,2)  NOT NULL DEFAULT 0,
    current_value     NUMERIC(18,2) NOT NULL DEFAULT 0,
    purchased_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    last_updated      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_holdings_customer ON portfolio_holdings(customer_id);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker   ON portfolio_holdings(ticker);

-- TABLE 5: transactions
CREATE TABLE IF NOT EXISTS transactions (
    txn_id        VARCHAR(12)   PRIMARY KEY,
    customer_id   VARCHAR(10)   NOT NULL
                  REFERENCES customers(customer_id),
    ticker        VARCHAR(10)   NOT NULL,
    txn_type      VARCHAR(10)   NOT NULL
                  CHECK (txn_type IN ('buy','sell','transfer')),
    txn_category  VARCHAR(15)   NOT NULL DEFAULT 'investment',
    quantity      NUMERIC(18,6) NOT NULL,
    price_at_txn  NUMERIC(18,4) NOT NULL,
    total_value   NUMERIC(18,2) NOT NULL,
    realized_pl   NUMERIC(18,2) NOT NULL DEFAULT 0,
    flagged       BOOLEAN       NOT NULL DEFAULT FALSE,
    txn_timestamp TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    ip_address    VARCHAR(45),
    geo_country   CHAR(2),
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_txn_customer  ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_txn_timestamp ON transactions(txn_timestamp);
CREATE INDEX IF NOT EXISTS idx_txn_flagged   ON transactions(flagged) WHERE flagged = TRUE;

-- TABLE 6: loans
CREATE TABLE IF NOT EXISTS loans (
    loan_id                  VARCHAR(12)   PRIMARY KEY,
    customer_id              VARCHAR(10)   NOT NULL
                             REFERENCES customers(customer_id),
    loan_type                VARCHAR(15)   NOT NULL
                             CHECK (loan_type IN ('mortgage','personal','margin','auto','student')),
    principal                NUMERIC(15,2) NOT NULL,
    interest_rate_pct        NUMERIC(6,2)  NOT NULL,
    outstanding_balance      NUMERIC(15,2) NOT NULL,
    emi_monthly              NUMERIC(12,2) NOT NULL,
    total_interest_paid_ytd  NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_principal_paid_ytd NUMERIC(12,2) NOT NULL DEFAULT 0,
    status                   VARCHAR(15)   NOT NULL DEFAULT 'current'
                             CHECK (status IN ('current','overdue','closed','deferred')),
    start_date               DATE          NOT NULL,
    next_due_date            DATE,
    created_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_loans_customer ON loans(customer_id);
CREATE INDEX IF NOT EXISTS idx_loans_status   ON loans(status);

-- TABLE 7: customer_summary
CREATE TABLE IF NOT EXISTS customer_summary (
    customer_id           VARCHAR(10)   PRIMARY KEY
                          REFERENCES customers(customer_id),
    portfolio_value       NUMERIC(18,2) NOT NULL DEFAULT 0,
    unrealized_pl         NUMERIC(18,2) NOT NULL DEFAULT 0,
    realized_pl           NUMERIC(18,2) NOT NULL DEFAULT 0,
    net_pl                NUMERIC(18,2) NOT NULL DEFAULT 0,
    cash_balance          NUMERIC(15,2) NOT NULL DEFAULT 0,
    loan_outstanding      NUMERIC(15,2) NOT NULL DEFAULT 0,
    interest_paid_ytd     NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_worth             NUMERIC(18,2) NOT NULL DEFAULT 0,
    stock_pct             NUMERIC(6,2)  NOT NULL DEFAULT 0,
    crypto_pct            NUMERIC(6,2)  NOT NULL DEFAULT 0,
    etf_pct               NUMERIC(6,2)  NOT NULL DEFAULT 0,
    cash_pct              NUMERIC(6,2)  NOT NULL DEFAULT 0,
    annualized_return_pct NUMERIC(8,2),
    sp500_return_pct      NUMERIC(8,2),
    last_refreshed        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- TABLE 8: alerts
CREATE TABLE IF NOT EXISTS alerts (
    alert_id    VARCHAR(12)  PRIMARY KEY,
    customer_id VARCHAR(10)  NOT NULL
                REFERENCES customers(customer_id),
    txn_id      VARCHAR(12)
                REFERENCES transactions(txn_id),
    alert_type  VARCHAR(20)  NOT NULL,
    severity    VARCHAR(10)  NOT NULL
                CHECK (severity IN ('low','medium','high','critical')),
    source      VARCHAR(15)  NOT NULL
                CHECK (source IN ('rule','ml_model')),
    description TEXT         NOT NULL,
    status      VARCHAR(15)  NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','review','resolved','escalated')),
    email_sent  BOOLEAN      NOT NULL DEFAULT FALSE,
    detected_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_customer ON alerts(customer_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status   ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_detected ON alerts(detected_at);

-- TABLE 9: reports
CREATE TABLE IF NOT EXISTS reports (
    report_id          VARCHAR(12)  PRIMARY KEY,
    customer_id        VARCHAR(10)  NOT NULL
                       REFERENCES customers(customer_id),
    report_type        VARCHAR(30)  NOT NULL,
    generated_by_agent VARCHAR(50)  NOT NULL,
    llm_used           VARCHAR(50)  NOT NULL,
    blob_url           TEXT         NOT NULL,
    pages              INTEGER,
    tokens_used        INTEGER,
    cost_usd           NUMERIC(8,4),
    generated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    email_sent         BOOLEAN      NOT NULL DEFAULT FALSE,
    sent_at            TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_customer ON reports(customer_id);

-- ═══════════════════════════════════════
-- TRIGGERS
-- ═══════════════════════════════════════

-- TRIGGER 1: market_prices → portfolio_holdings
CREATE OR REPLACE FUNCTION update_holdings_on_price_change()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE portfolio_holdings
    SET
        current_price     = NEW.price_usd,
        unrealized_pl     = ROUND(((NEW.price_usd - avg_buy_price) * quantity)::NUMERIC, 2),
        unrealized_pl_pct = ROUND((((NEW.price_usd - avg_buy_price) / NULLIF(avg_buy_price, 0)) * 100)::NUMERIC, 2),
        current_value     = ROUND((NEW.price_usd * quantity)::NUMERIC, 2),
        last_updated      = NOW()
    WHERE ticker = NEW.ticker AND asset_type != 'cash';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_price_to_holdings ON market_prices;
CREATE TRIGGER trg_price_to_holdings
AFTER UPDATE OF price_usd ON market_prices
FOR EACH ROW
EXECUTE FUNCTION update_holdings_on_price_change();

-- TRIGGER 2: portfolio_holdings → customer_summary
CREATE OR REPLACE FUNCTION update_customer_summary()
RETURNS TRIGGER AS $$
DECLARE
    v_cid      VARCHAR(20) := NEW.customer_id;
    v_port     NUMERIC(18,2);
    v_unreal   NUMERIC(18,2);
    v_realized NUMERIC(18,2);
    v_cash     NUMERIC(15,2);
    v_loan     NUMERIC(15,2);
    v_int      NUMERIC(12,2);
    v_net_pl   NUMERIC(18,2);
    v_worth    NUMERIC(18,2);
    v_stk      NUMERIC(6,2);
    v_cry      NUMERIC(6,2);
    v_etf      NUMERIC(6,2);
    v_csh      NUMERIC(6,2);
BEGIN
    SELECT COALESCE(SUM(current_value), 0) INTO v_port
    FROM portfolio_holdings WHERE customer_id = v_cid AND asset_type != 'cash';

    SELECT COALESCE(SUM(unrealized_pl), 0) INTO v_unreal
    FROM portfolio_holdings WHERE customer_id = v_cid AND asset_type != 'cash';

    SELECT COALESCE(SUM(realized_pl), 0) INTO v_realized
    FROM transactions WHERE customer_id = v_cid AND txn_type = 'sell';

    SELECT COALESCE(SUM(current_value), 0) INTO v_cash
    FROM portfolio_holdings WHERE customer_id = v_cid AND asset_type = 'cash';

    SELECT COALESCE(SUM(outstanding_balance), 0) INTO v_loan
    FROM loans WHERE customer_id = v_cid AND status != 'closed';

    SELECT COALESCE(SUM(total_interest_paid_ytd), 0) INTO v_int
    FROM loans WHERE customer_id = v_cid;

    v_net_pl := v_unreal + v_realized - v_int;
    v_worth  := v_port + v_cash - v_loan;

    SELECT
        ROUND(COALESCE(SUM(CASE WHEN asset_type='stock'  THEN current_value ELSE 0 END) / NULLIF(v_port,0)*100, 0),1),
        ROUND(COALESCE(SUM(CASE WHEN asset_type='crypto' THEN current_value ELSE 0 END) / NULLIF(v_port,0)*100, 0),1),
        ROUND(COALESCE(SUM(CASE WHEN asset_type='etf'    THEN current_value ELSE 0 END) / NULLIF(v_port,0)*100, 0),1),
        ROUND(COALESCE(SUM(CASE WHEN asset_type='cash'   THEN current_value ELSE 0 END) / NULLIF(v_port,0)*100, 0),1)
    INTO v_stk, v_cry, v_etf, v_csh
    FROM portfolio_holdings WHERE customer_id = v_cid;

    INSERT INTO customer_summary (
        customer_id, portfolio_value, unrealized_pl, realized_pl, net_pl,
        cash_balance, loan_outstanding, interest_paid_ytd, net_worth,
        stock_pct, crypto_pct, etf_pct, cash_pct, last_refreshed
    ) VALUES (
        v_cid, v_port, v_unreal, v_realized, v_net_pl,
        v_cash, v_loan, v_int, v_worth,
        v_stk, v_cry, v_etf, v_csh, NOW()
    )
    ON CONFLICT (customer_id) DO UPDATE SET
        portfolio_value   = EXCLUDED.portfolio_value,
        unrealized_pl     = EXCLUDED.unrealized_pl,
        realized_pl       = EXCLUDED.realized_pl,
        net_pl            = EXCLUDED.net_pl,
        cash_balance      = EXCLUDED.cash_balance,
        loan_outstanding  = EXCLUDED.loan_outstanding,
        interest_paid_ytd = EXCLUDED.interest_paid_ytd,
        net_worth         = EXCLUDED.net_worth,
        stock_pct         = EXCLUDED.stock_pct,
        crypto_pct        = EXCLUDED.crypto_pct,
        etf_pct           = EXCLUDED.etf_pct,
        cash_pct          = EXCLUDED.cash_pct,
        last_refreshed    = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_holdings_to_summary ON portfolio_holdings;
CREATE TRIGGER trg_holdings_to_summary
AFTER UPDATE OF current_value ON portfolio_holdings
FOR EACH ROW
EXECUTE FUNCTION update_customer_summary();

-- TRIGGER 3: customer_summary → WebSocket notify
CREATE OR REPLACE FUNCTION notify_dashboard()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('dashboard_update',
        json_build_object(
            'customer_id',    NEW.customer_id,
            'portfolio_value',NEW.portfolio_value,
            'unrealized_pl',  NEW.unrealized_pl,
            'net_pl',         NEW.net_pl,
            'net_worth',      NEW.net_worth,
            'stock_pct',      NEW.stock_pct,
            'crypto_pct',     NEW.crypto_pct,
            'etf_pct',        NEW.etf_pct,
            'cash_pct',       NEW.cash_pct,
            'last_refreshed', NEW.last_refreshed
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_summary_to_ws ON customer_summary;
CREATE TRIGGER trg_summary_to_ws
AFTER INSERT OR UPDATE ON customer_summary
FOR EACH ROW
EXECUTE FUNCTION notify_dashboard();

-- TRIGGER 4: auto risk breach alert
CREATE OR REPLACE FUNCTION check_risk_breach()
RETURNS TRIGGER AS $$
DECLARE
    v_risk  VARCHAR(20);
    v_limit NUMERIC(5,2);
BEGIN
    SELECT risk_profile INTO v_risk
    FROM customers WHERE customer_id = NEW.customer_id;

    v_limit := CASE v_risk
        WHEN 'conservative' THEN 10.0
        WHEN 'moderate'     THEN 25.0
        WHEN 'aggressive'   THEN 50.0
        ELSE 25.0
    END;

    IF NEW.crypto_pct > v_limit THEN
        INSERT INTO alerts (
            alert_id, customer_id, alert_type, severity, source, description, detected_at, updated_at
        ) VALUES (
            'ALT-R-' || SUBSTR(MD5(NEW.customer_id || NOW()::text), 1, 6),
            NEW.customer_id,
            'risk_breach',
            CASE WHEN NEW.crypto_pct > v_limit * 1.5 THEN 'high' ELSE 'medium' END,
            'rule',
            FORMAT('Crypto %s%% exceeds %s profile limit of %s%%', NEW.crypto_pct, v_risk, v_limit),
            NOW(), NOW()
        )
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_risk_breach ON customer_summary;
CREATE TRIGGER trg_risk_breach
AFTER INSERT OR UPDATE OF crypto_pct ON customer_summary
FOR EACH ROW
EXECUTE FUNCTION check_risk_breach();

-- ═══════════════════════════════════════
-- SEED DATA
-- ═══════════════════════════════════════

-- ADMINS (passwords: Admin@123, Admin@456, Admin@789)
INSERT INTO admins VALUES
('ADM-001','Priya Sharma','priya@finsight.com',
 '$2b$12$V72pss8olG1emUbDUIg5EOIxM2DaLgR11n2l9onqQd6EeDqFgR58S',
 'senior_advisor',TRUE,
 '2025-04-19 09:01:00+00','2021-03-01 00:00:00+00'),
('ADM-002','Marcus Chen','marcus@finsight.com',
 '$2b$12$SXlrCowaEjZ76qG/TvckPOwU8ZK1blrcDAW2b3WryjEiqTGe/eJDq',
 'advisor',TRUE,
 '2025-04-19 08:45:00+00','2022-06-15 00:00:00+00'),
('ADM-003','Laura Voss','laura@finsight.com',
 '$2b$12$s4JyyFR57BjJib.3G.2G5eXimBV2I8oWyDznU9yWGEoYh8FrLSOuq',
 'junior_advisor',TRUE,
 '2025-04-15 11:20:00+00','2023-01-10 00:00:00+00')
ON CONFLICT DO NOTHING;

-- CUSTOMERS (passwords: Cust@0001 through Cust@0050)
INSERT INTO customers VALUES
('CUS-0001','Arjun','Mehta','arjun.meh@gmail.com',
 crypt('Cust@0001',gen_salt('bf')),
 'moderate','premium','2019-03-14',
 '2025-04-19 08:30:00+00','US',TRUE,
 '2019-03-14 10:00:00+00'),
('CUS-0002','Sofia','Reyes','sofia.rey@outlook.com',
 crypt('Cust@0002',gen_salt('bf')),
 'aggressive','standard','2021-07-02',
 '2025-04-18 14:22:00+00','UK',TRUE,
 '2021-07-02 09:00:00+00'),
('CUS-0003','James','Okafor','james.oka@corp.com',
 crypt('Cust@0003',gen_salt('bf')),
 'conservative','premium','2017-11-28',
 '2025-04-17 19:05:00+00','CA',TRUE,
 '2017-11-28 08:00:00+00'),
('CUS-0004','Emily','Walsh','emily.wal@yahoo.com',
 crypt('Cust@0004',gen_salt('bf')),
 'moderate','standard','2020-05-10',
 '2025-04-19 07:15:00+00','AU',TRUE,
 '2020-05-10 11:00:00+00'),
('CUS-0005','Ravi','Patel','ravi.pate@icloud.com',
 crypt('Cust@0005',gen_salt('bf')),
 'aggressive','elite','2018-09-22',
 '2025-04-19 06:44:00+00','IN',TRUE,
 '2018-09-22 07:30:00+00'),
('CUS-0006','Mei','Zhang','mei.zhan@gmail.com',
 crypt('Cust@0006',gen_salt('bf')),
 'conservative','standard','2022-01-15',
 '2025-04-16 12:00:00+00','SG',TRUE,
 '2022-01-15 10:00:00+00'),
('CUS-0007','Carlos','Gomez','carlos.gom@outlook.com',
 crypt('Cust@0007',gen_salt('bf')),
 'moderate','premium','2020-11-03',
 '2025-04-18 09:30:00+00','AE',TRUE,
 '2020-11-03 09:00:00+00'),
('CUS-0008','Amara','Diallo','amara.dia@corp.com',
 crypt('Cust@0008',gen_salt('bf')),
 'aggressive','standard','2023-03-20',
 '2025-04-17 16:45:00+00','DE',TRUE,
 '2023-03-20 08:00:00+00'),
('CUS-0009','Liam','Turner','liam.turn@yahoo.com',
 crypt('Cust@0009',gen_salt('bf')),
 'conservative','elite','2016-08-11',
 '2025-04-19 10:00:00+00','FR',TRUE,
 '2016-08-11 07:00:00+00'),
('CUS-0010','Fatima','Hassan','fatima.has@icloud.com',
 crypt('Cust@0010',gen_salt('bf')),
 'moderate','standard','2021-12-05',
 '2025-04-18 11:30:00+00','NL',TRUE,
 '2021-12-05 09:30:00+00'),
('CUS-0011','Noah','Brown','noah.brow@gmail.com',
 crypt('Cust@0011',gen_salt('bf')),
 'aggressive','premium','2020-04-17',
 '2025-04-15 08:00:00+00','US',TRUE,
 '2020-04-17 10:00:00+00'),
('CUS-0012','Yuki','Tanaka','yuki.tana@outlook.com',
 crypt('Cust@0012',gen_salt('bf')),
 'conservative','standard','2019-07-30',
 '2025-04-14 14:00:00+00','UK',TRUE,
 '2019-07-30 09:00:00+00'),
('CUS-0013','Andre','Dubois','andre.dub@corp.com',
 crypt('Cust@0013',gen_salt('bf')),
 'moderate','elite','2018-02-14',
 '2025-04-19 09:15:00+00','CA',TRUE,
 '2018-02-14 08:00:00+00'),
('CUS-0014','Priya','Sharma','priya.sha@yahoo.com',
 crypt('Cust@0014',gen_salt('bf')),
 'aggressive','standard','2022-08-09',
 '2025-04-18 17:00:00+00','AU',TRUE,
 '2022-08-09 10:00:00+00'),
('CUS-0015','Ethan','Clark','ethan.cla@icloud.com',
 crypt('Cust@0015',gen_salt('bf')),
 'conservative','premium','2017-05-25',
 '2025-04-17 20:30:00+00','IN',TRUE,
 '2017-05-25 07:00:00+00'),
('CUS-0016','Layla','Al-Amin','layla.al@gmail.com',
 crypt('Cust@0016',gen_salt('bf')),
 'moderate','standard','2021-03-08',
 '2025-04-16 13:00:00+00','SG',TRUE,
 '2021-03-08 09:00:00+00'),
('CUS-0017','Omar','Nasser','omar.nass@outlook.com',
 crypt('Cust@0017',gen_salt('bf')),
 'aggressive','elite','2019-10-14',
 '2025-04-19 07:45:00+00','AE',TRUE,
 '2019-10-14 08:00:00+00'),
('CUS-0018','Chloe','Martin','chloe.mar@corp.com',
 crypt('Cust@0018',gen_salt('bf')),
 'conservative','standard','2023-01-22',
 '2025-04-18 10:15:00+00','DE',TRUE,
 '2023-01-22 10:00:00+00'),
('CUS-0019','Diego','Torres','diego.tor@yahoo.com',
 crypt('Cust@0019',gen_salt('bf')),
 'moderate','premium','2020-09-01',
 '2025-04-17 15:00:00+00','FR',TRUE,
 '2020-09-01 09:30:00+00'),
('CUS-0020','Aisha','Rahman','aisha.rah@icloud.com',
 crypt('Cust@0020',gen_salt('bf')),
 'aggressive','standard','2022-04-18',
 '2025-04-19 08:00:00+00','NL',TRUE,
 '2022-04-18 08:00:00+00'),
('CUS-0021','Lucas','Silva','lucas.sil@gmail.com',
 crypt('Cust@0021',gen_salt('bf')),
 'conservative','elite','2018-06-30',
 '2025-04-18 09:00:00+00','US',TRUE,
 '2018-06-30 07:30:00+00'),
('CUS-0022','Hana','Kimura','hana.kimu@outlook.com',
 crypt('Cust@0022',gen_salt('bf')),
 'moderate','standard','2021-11-11',
 '2025-04-17 11:00:00+00','UK',TRUE,
 '2021-11-11 10:00:00+00'),
('CUS-0023','Felix','Weber','felix.web@corp.com',
 crypt('Cust@0023',gen_salt('bf')),
 'aggressive','premium','2020-02-28',
 '2025-04-16 16:00:00+00','CA',TRUE,
 '2020-02-28 09:00:00+00'),
('CUS-0024','Nina','Petrov','nina.petr@yahoo.com',
 crypt('Cust@0024',gen_salt('bf')),
 'conservative','standard','2019-04-05',
 '2025-04-15 14:30:00+00','AU',TRUE,
 '2019-04-05 08:00:00+00'),
('CUS-0025','Sam','Jones','sam.jone@icloud.com',
 crypt('Cust@0025',gen_salt('bf')),
 'moderate','elite','2017-12-19',
 '2025-04-19 10:30:00+00','IN',TRUE,
 '2017-12-19 07:00:00+00'),
('CUS-0026','Zara','Khan','zara.khan@gmail.com',
 crypt('Cust@0026',gen_salt('bf')),
 'aggressive','standard','2022-07-07',
 '2025-04-18 08:15:00+00','SG',TRUE,
 '2022-07-07 09:30:00+00'),
('CUS-0027','Ben','Cohen','ben.cohe@outlook.com',
 crypt('Cust@0027',gen_salt('bf')),
 'conservative','premium','2020-03-15',
 '2025-04-17 13:45:00+00','AE',TRUE,
 '2020-03-15 10:00:00+00'),
('CUS-0028','Nora','Ivanova','nora.ivan@corp.com',
 crypt('Cust@0028',gen_salt('bf')),
 'moderate','standard','2021-09-23',
 '2025-04-16 10:00:00+00','DE',TRUE,
 '2021-09-23 09:00:00+00'),
('CUS-0029','Ivan','Novak','ivan.nova@yahoo.com',
 crypt('Cust@0029',gen_salt('bf')),
 'aggressive','elite','2018-01-07',
 '2025-04-19 07:30:00+00','FR',TRUE,
 '2018-01-07 08:00:00+00'),
('CUS-0030','Sara','Ali','sara.ali@icloud.com',
 crypt('Cust@0030',gen_salt('bf')),
 'conservative','standard','2023-05-14',
 '2025-04-18 12:00:00+00','NL',TRUE,
 '2023-05-14 10:00:00+00'),
('CUS-0031','Jack','Moore','jack.moor@gmail.com',
 crypt('Cust@0031',gen_salt('bf')),
 'moderate','premium','2019-08-26',
 '2025-04-17 09:00:00+00','US',TRUE,
 '2019-08-26 09:00:00+00'),
('CUS-0032','Mia','Flores','mia.flor@outlook.com',
 crypt('Cust@0032',gen_salt('bf')),
 'aggressive','standard','2021-06-13',
 '2025-04-16 11:30:00+00','UK',TRUE,
 '2021-06-13 10:00:00+00'),
('CUS-0033','Raj','Gupta','raj.gupt@corp.com',
 crypt('Cust@0033',gen_salt('bf')),
 'conservative','elite','2017-03-21',
 '2025-04-19 08:45:00+00','CA',TRUE,
 '2017-03-21 07:30:00+00'),
('CUS-0034','Leila','Mansour','leila.man@yahoo.com',
 crypt('Cust@0034',gen_salt('bf')),
 'moderate','standard','2022-10-04',
 '2025-04-18 15:30:00+00','AU',TRUE,
 '2022-10-04 09:00:00+00'),
('CUS-0035','Tom','Hill','tom.hill@icloud.com',
 crypt('Cust@0035',gen_salt('bf')),
 'aggressive','premium','2020-07-19',
 '2025-04-17 18:00:00+00','IN',TRUE,
 '2020-07-19 08:30:00+00'),
('CUS-0036','Yara','Sahin','yara.sahi@gmail.com',
 crypt('Cust@0036',gen_salt('bf')),
 'conservative','standard','2021-02-28',
 '2025-04-16 09:30:00+00','SG',TRUE,
 '2021-02-28 10:00:00+00'),
('CUS-0037','Ali','Hussein','ali.huss@outlook.com',
 crypt('Cust@0037',gen_salt('bf')),
 'aggressive','elite','2019-05-17',
 '2025-04-19 09:30:00+00','AE',TRUE,
 '2019-05-17 09:00:00+00'),
('CUS-0038','Ines','Carvalho','ines.carv@corp.com',
 crypt('Cust@0038',gen_salt('bf')),
 'aggressive','standard','2023-02-09',
 '2025-04-18 13:00:00+00','DE',TRUE,
 '2023-02-09 08:00:00+00'),
('CUS-0039','Leo','Grant','leo.gran@yahoo.com',
 crypt('Cust@0039',gen_salt('bf')),
 'conservative','premium','2018-11-30',
 '2025-04-17 10:15:00+00','FR',TRUE,
 '2018-11-30 07:00:00+00'),
('CUS-0040','Maya','Singh','maya.sing@icloud.com',
 crypt('Cust@0040',gen_salt('bf')),
 'moderate','standard','2021-08-16',
 '2025-04-16 14:30:00+00','NL',TRUE,
 '2021-08-16 09:30:00+00'),
('CUS-0041','Max','Muller','max.mull@gmail.com',
 crypt('Cust@0041',gen_salt('bf')),
 'aggressive','elite','2020-01-25',
 '2025-04-19 08:00:00+00','US',TRUE,
 '2020-01-25 10:00:00+00'),
('CUS-0042','Rosa','Santos','rosa.sant@outlook.com',
 crypt('Cust@0042',gen_salt('bf')),
 'conservative','standard','2019-06-08',
 '2025-04-18 07:45:00+00','UK',TRUE,
 '2019-06-08 09:00:00+00'),
('CUS-0043','Kim','Park','kim.park@corp.com',
 crypt('Cust@0043',gen_salt('bf')),
 'moderate','premium','2022-03-27',
 '2025-04-17 12:30:00+00','CA',TRUE,
 '2022-03-27 08:30:00+00'),
('CUS-0044','Dan','Evans','dan.evan@yahoo.com',
 crypt('Cust@0044',gen_salt('bf')),
 'aggressive','standard','2020-10-12',
 '2025-04-16 16:45:00+00','AU',TRUE,
 '2020-10-12 09:00:00+00'),
('CUS-0045','Ava','Chen','ava.chen@icloud.com',
 crypt('Cust@0045',gen_salt('bf')),
 'conservative','elite','2017-07-04',
 '2025-04-19 10:00:00+00','IN',TRUE,
 '2017-07-04 07:30:00+00'),
('CUS-0046','Chen','Wu','chen.wu@gmail.com',
 crypt('Cust@0046',gen_salt('bf')),
 'moderate','standard','2021-04-20',
 '2025-04-18 09:45:00+00','SG',TRUE,
 '2021-04-20 10:00:00+00'),
('CUS-0047','Tara','Nair','tara.nair@outlook.com',
 crypt('Cust@0047',gen_salt('bf')),
 'aggressive','premium','2020-08-31',
 '2025-04-17 14:00:00+00','AE',TRUE,
 '2020-08-31 09:00:00+00'),
('CUS-0048','Erik','Larsson','erik.lars@corp.com',
 crypt('Cust@0048',gen_salt('bf')),
 'conservative','standard','2019-01-15',
 '2025-04-16 10:30:00+00','DE',TRUE,
 '2019-01-15 08:00:00+00'),
('CUS-0049','Lena','Bauer','lena.baue@yahoo.com',
 crypt('Cust@0049',gen_salt('bf')),
 'moderate','elite','2022-06-02',
 '2025-04-19 09:00:00+00','FR',TRUE,
 '2022-06-02 09:30:00+00'),
('CUS-0050','Jay','Das','jay.das@icloud.com',
 crypt('Cust@0050',gen_salt('bf')),
 'aggressive','standard','2021-10-28',
 '2025-04-18 16:00:00+00','NL',TRUE,
 '2021-10-28 10:00:00+00')
ON CONFLICT DO NOTHING;

-- PORTFOLIO HOLDINGS
-- avg_buy_price values are historical — realistic past prices.
-- current_price starts same as market_prices seed value
-- but will be overwritten by Trigger 1 within 60 seconds.
-- quantity and avg_buy_price never change automatically.
INSERT INTO portfolio_holdings VALUES
('HOL-0001','CUS-0001','CASH','cash',1,18500,18500,0,0,18500,'2019-03-14 10:00:00+00',NOW()),
('HOL-0002','CUS-0001','NVDA','stock',120,421.50,874.30,54336,107.32,104916,'2021-06-15 09:31:00+00',NOW()),
('HOL-0003','CUS-0001','BTC','crypto',0.85,38200,67400,24820,76.49,57290,'2020-11-02 14:20:00+00',NOW()),
('HOL-0004','CUS-0001','VTSAX','etf',310,98.40,112.70,4433,14.53,34937,'2022-01-10 10:05:00+00',NOW()),
('HOL-0005','CUS-0001','MSFT','stock',50,310.00,415.00,5250,33.87,20750,'2020-03-20 11:00:00+00',NOW()),
('HOL-0006','CUS-0002','CASH','cash',1,12000,12000,0,0,12000,'2021-07-02 09:00:00+00',NOW()),
('HOL-0007','CUS-0002','TSLA','stock',200,265.00,182.40,-16520,-31.17,36480,'2021-09-10 09:45:00+00',NOW()),
('HOL-0008','CUS-0002','BTC','crypto',1.5,38200,67400,43800,76.49,101100,'2021-01-15 08:30:00+00',NOW()),
('HOL-0009','CUS-0002','SOL','crypto',25,45.00,185.00,3500,311.11,4625,'2022-03-01 11:00:00+00',NOW()),
('HOL-0010','CUS-0002','META','stock',30,320.00,540.00,6600,68.75,16200,'2022-11-01 10:00:00+00',NOW()),
('HOL-0011','CUS-0003','CASH','cash',1,35000,35000,0,0,35000,'2017-11-28 08:00:00+00',NOW()),
('HOL-0012','CUS-0003','AAPL','stock',80,178.00,229.00,4080,28.65,18320,'2020-08-05 10:30:00+00',NOW()),
('HOL-0013','CUS-0003','SPY','etf',60,430.00,540.00,6600,25.58,32400,'2019-02-14 09:00:00+00',NOW()),
('HOL-0014','CUS-0003','ETH','crypto',4.2,1820.00,3410.00,6678,87.36,14322,'2021-05-10 13:45:00+00',NOW()),
('HOL-0015','CUS-0004','CASH','cash',1,9500,9500,0,0,9500,'2020-05-10 11:00:00+00',NOW()),
('HOL-0016','CUS-0004','MSFT','stock',30,310.00,415.00,3150,33.87,12450,'2021-03-12 10:00:00+00',NOW()),
('HOL-0017','CUS-0004','QQQ','etf',25,360.00,470.00,2750,30.56,11750,'2022-06-01 09:30:00+00',NOW()),
('HOL-0018','CUS-0005','CASH','cash',1,22000,22000,0,0,22000,'2018-09-22 07:30:00+00',NOW()),
('HOL-0019','CUS-0005','NVDA','stock',75,421.50,874.30,33907.50,107.32,65572.50,'2021-08-20 09:00:00+00',NOW()),
('HOL-0020','CUS-0005','BTC','crypto',2.1,38200,67400,61320,76.49,141540,'2019-12-10 10:15:00+00',NOW()),
('HOL-0021','CUS-0005','META','stock',40,320.00,540.00,8800,68.75,21600,'2022-11-05 11:00:00+00',NOW()),
('HOL-0022','CUS-0006','CASH','cash',1,15000,15000,0,0,15000,'2022-01-15 10:00:00+00',NOW()),
('HOL-0023','CUS-0006','SPY','etf',40,430.00,540.00,4400,25.58,21600,'2022-02-01 09:00:00+00',NOW()),
('HOL-0024','CUS-0006','AAPL','stock',20,178.00,229.00,1020,28.65,4580,'2022-03-10 10:00:00+00',NOW()),
('HOL-0025','CUS-0007','CASH','cash',1,11000,11000,0,0,11000,'2020-11-03 09:00:00+00',NOW()),
('HOL-0026','CUS-0007','NVDA','stock',30,421.50,874.30,13581,107.32,26229,'2022-01-05 09:30:00+00',NOW()),
('HOL-0027','CUS-0007','ETH','crypto',2.0,1820.00,3410.00,3180,87.36,6820,'2021-06-15 10:00:00+00',NOW()),
('HOL-0028','CUS-0007','VTSAX','etf',100,98.40,112.70,1430,14.53,11270,'2021-07-01 09:00:00+00',NOW()),
('HOL-0029','CUS-0008','CASH','cash',1,8000,8000,0,0,8000,'2023-03-20 08:00:00+00',NOW()),
('HOL-0030','CUS-0008','TSLA','stock',50,265.00,182.40,-4130,-31.17,9120,'2023-04-01 09:00:00+00',NOW()),
('HOL-0031','CUS-0008','SOL','crypto',15,45.00,185.00,2100,311.11,2775,'2023-05-01 10:00:00+00',NOW()),
('HOL-0032','CUS-0009','CASH','cash',1,42000,42000,0,0,42000,'2016-08-11 07:00:00+00',NOW()),
('HOL-0033','CUS-0009','SPY','etf',100,430.00,540.00,11000,25.58,54000,'2018-01-10 09:00:00+00',NOW()),
('HOL-0034','CUS-0009','QQQ','etf',50,360.00,470.00,5500,30.56,23500,'2019-03-15 09:00:00+00',NOW()),
('HOL-0035','CUS-0010','CASH','cash',1,13500,13500,0,0,13500,'2021-12-05 09:30:00+00',NOW()),
('HOL-0036','CUS-0010','AAPL','stock',45,178.00,229.00,2295,28.65,10305,'2021-12-20 10:00:00+00',NOW()),
('HOL-0037','CUS-0010','MSFT','stock',25,310.00,415.00,2625,33.87,10375,'2022-01-10 09:30:00+00',NOW()),
('HOL-0038','CUS-0010','BNB','crypto',3.0,280.00,610.00,990,117.86,1830,'2022-02-01 10:00:00+00',NOW())
ON CONFLICT DO NOTHING;

-- Add holdings for CUS-0011 through CUS-0050
-- Generate at least 2-4 holdings per remaining customer
-- following the same pattern. Mix asset types based on risk_profile:
-- conservative: mostly SPY/QQQ/VTSAX ETFs, some AAPL/MSFT
-- moderate: mix of stocks + ETFs + small crypto
-- aggressive: NVDA/TSLA/META stocks + BTC/ETH/SOL crypto
-- Every customer must have a CASH row.
-- Use realistic avg_buy_price values (historical prices, 
-- not current prices).
-- Generate holdings for all remaining 40 customers 
-- (CUS-0011 through CUS-0050) following the exact same
-- INSERT format as above.

-- MARKET PRICES
-- IMPORTANT: These are seed/starting values only.
-- The yfinance scheduler will overwrite these with
-- real live prices within 60 seconds of app startup.
-- Never use these values for any calculation in app code.
INSERT INTO market_prices VALUES
('NVDA','stock',874.3000,855.20,2.24,'48M','$2.15T',
 6.2,88,NOW(),NOW()),
('TSLA','stock',182.4000,185.90,-1.88,'112M','$580B',
 -2.1,71,NOW(),NOW()),
('AAPL','stock',229.0000,225.40,1.60,'61M','$3.5T',
 1.8,79,NOW(),NOW()),
('MSFT','stock',415.0000,408.70,1.54,'22M','$3.1T',
 3.4,85,NOW(),NOW()),
('AMZN','stock',195.0000,191.20,1.99,'35M','$2.0T',
 2.0,76,NOW(),NOW()),
('GOOGL','stock',175.0000,176.10,-0.62,'28M','$2.2T',
 -0.5,63,NOW(),NOW()),
('META','stock',540.0000,527.30,2.41,'19M','$1.4T',
 5.1,82,NOW(),NOW()),
('VTSAX','etf',112.7000,111.90,0.71,'3M',NULL,
 0.9,91,NOW(),NOW()),
('SPY','etf',540.0000,535.60,0.82,'85M',NULL,
 1.1,90,NOW(),NOW()),
('QQQ','etf',470.0000,464.20,1.25,'42M',NULL,
 1.3,87,NOW(),NOW()),
('BTC','crypto',67400.0000,65200.00,3.37,'$38B','$1.32T',
 5.8,74,NOW(),NOW()),
('ETH','crypto',3410.0000,3425.00,-0.44,'$18B','$410B',
 1.3,68,NOW(),NOW()),
('SOL','crypto',185.0000,178.50,3.64,'$9B','$85B',
 7.2,65,NOW(),NOW()),
('BNB','crypto',610.0000,618.30,-1.34,'$4B','$90B',
 -1.0,62,NOW(),NOW())
ON CONFLICT DO NOTHING;
