-- Gap reports: RPT-0026 to RPT-0040 (15 rows)
-- Covers even-numbered customers not in initial seed
-- Mix: portfolio_summary(4), risk_analysis(4), tax_summary(4), performance_review(3)
-- Agents: agent-1/2/3; LLMs: gpt-4, claude-3, gemini-pro
INSERT INTO reports
    (report_id, customer_id, report_type, generated_by_agent, llm_used,
     blob_url, pages, tokens_used, cost_usd, email_sent, generated_at, sent_at, created_at)
VALUES
('RPT-0026','CUS-0002','portfolio_summary','agent-2','gpt-4','https://blob.example.com/rpt-0026.pdf',13,9200,2.60,TRUE,'2024-04-18 10:00:00+00','2024-04-18 10:45:00+00','2024-04-18 10:05:00+00'),
('RPT-0027','CUS-0004','risk_analysis','agent-1','claude-3','https://blob.example.com/rpt-0027.pdf',14,10800,3.05,FALSE,'2024-04-15 14:30:00+00',NULL,'2024-04-15 14:35:00+00'),
('RPT-0028','CUS-0006','tax_summary','agent-3','gemini-pro','https://blob.example.com/rpt-0028.pdf',11,7400,2.10,TRUE,'2024-04-12 09:15:00+00','2024-04-12 10:00:00+00','2024-04-12 09:20:00+00'),
('RPT-0029','CUS-0008','performance_review','agent-2','gpt-4','https://blob.example.com/rpt-0029.pdf',15,11500,3.20,FALSE,'2024-04-10 11:00:00+00',NULL,'2024-04-10 11:05:00+00'),
('RPT-0030','CUS-0010','portfolio_summary','agent-1','claude-3','https://blob.example.com/rpt-0030.pdf',16,12200,3.45,TRUE,'2024-04-08 13:30:00+00','2024-04-08 14:15:00+00','2024-04-08 13:35:00+00'),
('RPT-0031','CUS-0012','risk_analysis','agent-3','gemini-pro','https://blob.example.com/rpt-0031.pdf',12,8600,2.45,TRUE,'2024-04-06 10:00:00+00','2024-04-06 10:45:00+00','2024-04-06 10:05:00+00'),
('RPT-0032','CUS-0014','tax_summary','agent-2','gpt-4','https://blob.example.com/rpt-0032.pdf',17,13100,3.65,FALSE,'2024-04-04 15:00:00+00',NULL,'2024-04-04 15:05:00+00'),
('RPT-0033','CUS-0016','performance_review','agent-1','claude-3','https://blob.example.com/rpt-0033.pdf',14,10500,2.95,TRUE,'2024-04-02 11:30:00+00','2024-04-02 12:15:00+00','2024-04-02 11:35:00+00'),
('RPT-0034','CUS-0018','portfolio_summary','agent-3','gpt-4','https://blob.example.com/rpt-0034.pdf',15,11800,3.30,TRUE,'2024-03-31 09:00:00+00','2024-03-31 09:45:00+00','2024-03-31 09:05:00+00'),
('RPT-0035','CUS-0020','risk_analysis','agent-2','gemini-pro','https://blob.example.com/rpt-0035.pdf',13,9500,2.70,FALSE,'2024-03-29 14:00:00+00',NULL,'2024-03-29 14:05:00+00'),
('RPT-0036','CUS-0022','tax_summary','agent-1','gpt-4','https://blob.example.com/rpt-0036.pdf',16,12400,3.50,TRUE,'2024-03-27 10:30:00+00','2024-03-27 11:15:00+00','2024-03-27 10:35:00+00'),
('RPT-0037','CUS-0024','performance_review','agent-3','claude-3','https://blob.example.com/rpt-0037.pdf',12,9000,2.55,TRUE,'2024-03-25 13:00:00+00','2024-03-25 13:45:00+00','2024-03-25 13:05:00+00'),
('RPT-0038','CUS-0026','portfolio_summary','agent-2','gpt-4','https://blob.example.com/rpt-0038.pdf',14,10200,2.85,FALSE,'2024-03-23 09:30:00+00',NULL,'2024-03-23 09:35:00+00'),
('RPT-0039','CUS-0028','risk_analysis','agent-1','gemini-pro','https://blob.example.com/rpt-0039.pdf',15,11200,3.15,TRUE,'2024-03-21 11:00:00+00','2024-03-21 11:45:00+00','2024-03-21 11:05:00+00'),
('RPT-0040','CUS-0030','tax_summary','agent-3','claude-3','https://blob.example.com/rpt-0040.pdf',13,9800,2.80,TRUE,'2024-03-19 14:30:00+00','2024-03-19 15:15:00+00','2024-03-19 14:35:00+00')
ON CONFLICT DO NOTHING;
