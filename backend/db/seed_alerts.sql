INSERT INTO alerts VALUES
('ALT-0001','CUS-0002',NULL,'risk_breach','high','rule','Crypto allocation 35.5% exceeds aggressive profile limit of 30%','open',TRUE,'2024-04-20 08:00:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0002','CUS-0005',NULL,'risk_breach','medium','rule','Crypto allocation 28% exceeds conservative profile limit of 10%','open',FALSE,'2024-04-19 14:30:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0003','CUS-0008','TXN-0030','suspicious_activity','high','ml_model','Unusual trading pattern detected','open',TRUE,'2024-04-18 16:45:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0004','CUS-0011',NULL,'risk_breach','high','rule','Crypto allocation 32% exceeds aggressive profile limit of 50%','open',FALSE,'2024-04-17 09:15:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0005','CUS-0014','TXN-0046','large_transaction','medium','rule','Large SOL transaction detected: $2900','open',FALSE,'2024-04-16 11:20:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0006','CUS-0017',NULL,'risk_breach','critical','rule','Crypto allocation 42% exceeds elite profile limit of 50%','open',TRUE,'2024-04-15 10:30:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0007','CUS-0020','TXN-0061','suspicious_activity','high','ml_model','Potential pump-and-dump scheme detected in TSLA','open',TRUE,'2024-04-14 13:45:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0008','CUS-0023',NULL,'risk_breach','medium','rule','Crypto allocation 28% exceeds conservative profile limit of 10%','open',FALSE,'2024-04-13 15:00:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0009','CUS-0029','TXN-0087','large_transaction','medium','rule','Large BTC transaction detected: $14000','open',FALSE,'2024-04-12 09:00:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0010','CUS-0032',NULL,'risk_breach','high','rule','Crypto allocation 35% exceeds standard profile limit of 15%','open',TRUE,'2024-04-11 14:20:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0011','CUS-0035','TXN-0103','suspicious_activity','medium','ml_model','Unusual transaction timing detected','open',FALSE,'2024-04-10 10:15:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0012','CUS-0038',NULL,'portfolio_rebalance','low','rule','Portfolio drift detected: recommend rebalancing','open',FALSE,'2024-04-09 11:30:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0013','CUS-0041','TXN-0117','large_transaction','high','rule','Large BTC transaction detected: $22000','open',TRUE,'2024-04-08 12:45:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0014','CUS-0044',NULL,'risk_breach','high','rule','Crypto allocation 42% exceeds standard profile limit of 15%','open',TRUE,'2024-04-07 16:00:00+00',NULL,'2024-04-21 10:00:00+00'),
('ALT-0015','CUS-0047','TXN-0134','suspicious_activity','medium','ml_model','Unusual trading pattern detected','open',FALSE,'2024-04-06 09:30:00+00',NULL,'2024-04-21 10:00:00+00')
ON CONFLICT DO NOTHING;
