"""Small samples of the real source formats, so pipeline tests never touch the network."""

# Shaped like AMFI's NAVAll.txt (October 2026 format, with Plan and Option columns), including
# the awkward cases seen in the real file.
NAV_ALL = """\
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

Axis Mutual Fund

120465;INF846K01DP8;-;Axis Large Cap Fund;Direct Plan;Growth;62.1500;15-Oct-2026
120466;INF846K01DQ6;INF846K01DR4;Axis Large Cap Fund;Direct Plan;IDCW;20.4100;15-Oct-2026
112277;INF846K01131;-;Axis Large Cap Fund;Regular Plan;Growth Option;55.0200;15-Oct-2026

Open Ended Schemes(Debt Scheme - Liquid Fund)

HDFC Mutual Fund

119091;INF179KB1HP9;-;HDFC Liquid Fund - Direct Plan - Growth Option;;;5012.34567891;15-Oct-2026
119092;INF179KB1HQ7;-;HDFC Liquid Fund - Regular Plan - Daily IDCW;;;1019.8800;15-Oct-2026
119093;INF179KB1HR5;-;HDFC Liquid Fund Segregated Portfolio;;;0;15-Oct-2026
119094;INF179KB1HS3;-;HDFC Liquid Fund Bonus;;;N.A.;15-Oct-2026

Open Ended Schemes(Other Scheme - Index Funds)

UTI Mutual Fund

120716;INF789F1AUV3;-;UTI  Nifty 50 Index Fund;Direct Plan;Growth;171.2000;14-Oct-2026
120716;INF789F1AUV3;-;UTI  Nifty 50 Index Fund;Direct Plan;Growth;172.0000;15-Oct-2026
120717;INF789F1AUW1;-;UTI Nifty 50 Index Fund;Regular Plan;Growth;160.1000;31-Sep-2026

Close Ended Schemes(Income/Debt Oriented Schemes - Fixed Term Plan)

ICICI Prudential Mutual Fund

128111;INF109KB1XS5;-;ICICI Prudential Fixed Maturity Plan-Series 73-830 Days Plan J;;;12.4137;07-Aug-2017
"""

# The same file one business day later: one NAV changed, the rest identical.
NAV_ALL_NEXT_DAY = NAV_ALL.replace("62.1500;15-Oct-2026", "63.0000;16-Oct-2026")

# mfapi.in history document (newest first, as served), with a duplicate and a bad row.
MFAPI_HISTORY = {
    "meta": {"scheme_code": 120465, "scheme_name": "Axis Large Cap Fund - Direct Plan - Growth"},
    "data": [
        {"date": "15-10-2026", "nav": "62.15000"},
        {"date": "14-10-2026", "nav": "61.90000"},
        {"date": "14-10-2026", "nav": "61.90000"},
        {"date": "13-10-2026", "nav": "N.A."},
        {"date": "10-10-2025", "nav": "50.00000"},
        {"date": "15-10-2021", "nav": "31.07500"},
    ],
}

# MOSPI CPI API records (newest first), including the duplicated 2013 months.
CPI_RECORDS = [
    {"year": 2025, "month": "December", "index": "198.0", "inflation": "1.33", "status": "F"},
    {"year": 2025, "month": "November", "index": "197.9", "inflation": "0.71", "status": "P"},
    {"year": 2024, "month": "December", "index": "195.4", "inflation": "5.22", "status": "F"},
    {"year": 2013, "month": "May", "index": "107.5", "inflation": "9.03", "status": "F"},
    {"year": 2013, "month": "May", "index": "106.9", "inflation": None, "status": "F"},
    {"year": 2013, "month": "April", "index": "106.1", "inflation": None, "status": "F"},
    {"year": 2013, "month": "April", "index": "106.7", "inflation": "9.10", "status": "F"},
    {"year": 2011, "month": "March", "index": None, "inflation": None, "status": "F"},
]
