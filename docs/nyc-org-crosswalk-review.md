# OTI agency registry (`t3jq-9nkf`) vs our org directory

All **306** organizations OTI publishes, and what each links to in `wegov_orgs`.
Built from the live `nyc_org_crosswalk` table, 2026-07-30. One-to-one enforced; 2 review rows accepted, 7 refused.

- **173 linked** - confident (exact/alias or token-set)
- **7 rejected** - reviewed and refused
- **126 no match** - import candidates

## Linked - 173

Includes borough/county equivalence (District Attorney - Kings <-> Brooklyn District Attorney's Office) and dropped legal suffixes (Health and Hospitals Corporation <-> NYC Health + Hospitals).

| OTI record_id | OTI name | type | our id | our name | tier | score |
|---|---|---|---|---|---|---|
| `NYC_GOID_000021` | Board of Correction | Advisory or Regulatory Organization | `170010073` | Board of Correction | exact/alias | 1.00 |
| `NYC_GOID_000023` | Board of Elections | Advisory or Regulatory Organization | `170010003` | Board of Elections | exact/alias | 1.00 |
| `NYC_GOID_000025` | Board of Standards and Appeals | Advisory or Regulatory Organization | `170019012` | Board of Standards And Appeals | exact/alias | 1.00 |
| `NYC_GOID_000040` | Business Integrity Commission | Advisory or Regulatory Organization | `170010829` | Business Integrity Commission | exact/alias | 1.00 |
| `NYC_GOID_000042` | Campaign Finance Board | Advisory or Regulatory Organization | `170010004` | Campaign Finance Board | exact/alias | 1.00 |
| `NYC_GOID_000096` | City Commission on Human Rights | Advisory or Regulatory Organization | `170010226` | Commission on Human Rights | exact/alias | 1.00 |
| `NYC_GOID_000098` | City Planning Commission | Advisory or Regulatory Organization | `170011002` | City Planning Commission | exact/alias | 1.00 |
| `NYC_GOID_000103` | Civil Service Commission | Advisory or Regulatory Organization | `170010134` | Civil Service Commission | exact/alias | 1.00 |
| `NYC_GOID_000105` | Civilian Complaint Review Board | Advisory or Regulatory Organization | `170010054` | Civilian Complaint Review Board | exact/alias | 1.00 |
| `NYC_GOID_000111` | Commission on Gender Equity | Advisory or Regulatory Organization | `170011004` | Commission on Gender Equity | exact/alias | 1.00 |
| `NYC_GOID_000109` | Commission to Combat Police Corruption | Advisory or Regulatory Organization | `170011005` | Commission to Combat Police Corruption | exact/alias | 1.00 |
| `NYC_GOID_000118` | Community Boards | Advisory or Regulatory Organization | `170010499` | Community Boards | exact/alias | 1.00 |
| `NYC_GOID_000119` | Community Services Board | Advisory or Regulatory Organization | `170010341` | Manhattan Community Board # 1 | token-set | 1.00 |
| `NYC_GOID_000124` | Conflicts of Interest Board | Advisory or Regulatory Organization | `170010312` | Conflicts of Interest Board | exact/alias | 1.00 |
| `NYC_GOID_000185` | Equal Employment Practices Commission | Advisory or Regulatory Organization | `170010133` | Equal Employment Practices Commission | exact/alias | 1.00 |
| `NYC_GOID_000190` | Financial Information Services Agency | Advisory or Regulatory Organization | `170010127` | Financial Information Services Agency | exact/alias | 1.00 |
| `NYC_GOID_000222` | Independent Budget Office | Advisory or Regulatory Organization | `170010132` | Independent Budget Office | exact/alias | 1.00 |
| `NYC_GOID_000236` | Landmarks Preservation Commission | Advisory or Regulatory Organization | `170010136` | Landmarks Preservation Commission | exact/alias | 1.00 |
| `NYC_GOID_000247` | Mayor's Committee on City Marshals | Advisory or Regulatory Organization | `170011035` | Mayor's Committee on City Marshals | exact/alias | 1.00 |
| `NYC_GOID_000240` | New York City Loft Board | Advisory or Regulatory Organization | `170011042` | New York City Loft Board | exact/alias | 1.00 |
| `NYC_GOID_000343` | New York City Office of the Actuary | Advisory or Regulatory Organization | `170010008` | Office of the Actuary | exact/alias | 1.00 |
| `NYC_GOID_100024` | New York City Tax Commission | Advisory or Regulatory Organization | `170019013` | New York City Tax Commission | exact/alias | 1.00 |
| `NYC_GOID_000345` | Office of Administrative Tax Appeals | Advisory or Regulatory Organization | `170010021` | Office of Administrative Tax Appeals | exact/alias | 1.00 |
| `NYC_GOID_000354` | Office of Collective Bargaining | Advisory or Regulatory Organization | `170010313` | Office of Collective Bargaining | exact/alias | 1.00 |
| `NYC_GOID_000392` | Procurement Policy Board | Advisory or Regulatory Organization | `170100006` | Procurement Policy Board | exact/alias | 1.00 |
| `NYC_GOID_000397` | Public Design Commission | Advisory or Regulatory Organization | `170020048` | Public Design Commission | exact/alias | 1.00 |
| `NYC_GOID_000408` | Rent Guidelines Board | Advisory or Regulatory Organization | `170019010` | Rent Guidelines Board | exact/alias | 1.00 |
| `NYC_GOID_000425` | Special Commissioner of Investigation for the New York City School District | Advisory or Regulatory Organization | `170011015` | Special Commissioner of Investigation for the NYC School District | token-set | 1.00 |
| `NYC_GOID_100023` | Tax Appeals Tribunal | Advisory or Regulatory Organization | `170019015` | Tax Appeals Tribunal | exact/alias | 1.00 |
| `NYC_GOID_000102` | Civic Engagement Commission | Division | `170019018` | Civic Engagement Commission | exact/alias | 1.00 |
| `NYC_GOID_100010` | Cyber Command | Division | `170100033` | NYC Cyber Command | exact/alias | 1.00 |
| `NYC_GOID_000155` | Department of Homeless Services | Division | `170010071` | Department of Homeless Services | exact/alias | 1.00 |
| `NYC_GOID_000156` | Human Resources Administration | Division | `170100013` | Human Resources Administration | exact/alias | 1.00 |
| `NYC_GOID_000259` | Mayor's Office of Animal Welfare | Division | `170100224` | Office of Animal Welfare | token-set | 1.00 |
| `NYC_GOID_000293` | Mayor's Public Engagement Unit | Division | `170100009` | Public Engagement Unit | token-set | 1.00 |
| `NYC_GOID_000328` | NYC Service | Division | `170011023` | NYC Service | exact/alias | 1.00 |
| `NYC_GOID_000000` | NYC311 | Division | `170100005` | NYC 311 | exact/alias | 1.00 |
| `NYC_GOID_100011` | Office of Data Analytics | Division | `170011007` | Office of Data Analytics | exact/alias | 1.00 |
| `NYC_GOID_100012` | Office of Information Privacy | Division | `170100237` | Office of Information Privacy | exact/alias | 1.00 |
| `NYC_GOID_100017` | Office of Nightlife | Division | `170100233` | Office of Nightlife | exact/alias | 1.00 |
| `NYC_GOID_100009` | Office of the City Clerk | Division | `170010103` | City Clerk | exact/alias | 1.00 |
| `NYC_GOID_100020` | Office of the Inspector General for the NYPD | Division | `170011048` | Office of the Inspector General for the NYPD | exact/alias | 1.00 |
| `NYC_GOID_100002` | Office of the Special Narcotics Prosecutor | Division | `170010906` | Office of Prosecutor & Special Narcotics | token-set | 1.00 |
| `NYC_GOID_100005` | Sheriff | Division | `170100239` | Sheriff | exact/alias | 1.00 |
| `NYC_GOID_100003` | Unity Project | Division | `170100015` | Unity Project | exact/alias | 1.00 |
| `NYC_GOID_000168` | Bronx District Attorney's Office | Elected Office | `170010902` | District Attorney - Bronx | token-set | 1.00 |
| `NYC_GOID_000169` | Brooklyn District Attorney's Office | Elected Office | `170010903` | District Attorney - Kings | token-set | 1.00 |
| `NYC_GOID_000170` | Manhattan District Attorney's Office | Elected Office | `170010901` | District Attorney - New York | token-set | 1.00 |
| `NYC_GOID_000097` | New York City Council | Elected Office | `170010102` | City Council | exact/alias | 1.00 |
| `NYC_GOID_000027` | Office of the Borough President of Brooklyn | Elected Office | `170010012` | Brooklyn Borough President | token-set | 1.00 |
| `NYC_GOID_000028` | Office of the Borough President of Manhattan | Elected Office | `170010010` | Manhattan Borough President | token-set | 1.00 |
| `NYC_GOID_000029` | Office of the Borough President of Queens | Elected Office | `170010013` | Queens Borough President | token-set | 1.00 |
| `NYC_GOID_000030` | Office of the Borough President of Staten Island | Elected Office | `170010014` | Staten Island Borough President | token-set | 1.00 |
| `NYC_GOID_000026` | Office of the Borough President of The Bronx | Elected Office | `170010011` | Bronx Borough President | token-set | 1.00 |
| `NYC_GOID_000251` | Office of the Mayor | Elected Office | `170010002` | Mayor's Office | exact/alias | 1.00 |
| `NYC_GOID_000123` | Office of the New York City Comptroller | Elected Office | `170010015` | Office of the Comptroller | exact/alias | 1.00 |
| `NYC_GOID_000396` | Office of the Public Advocate | Elected Office | `170010101` | Public Advocate | exact/alias | 1.00 |
| `NYC_GOID_000171` | Queens District Attorney's Office | Elected Office | `170010904` | District Attorney - Queens | token-set | 1.00 |
| `NYC_GOID_000172` | Staten Island District Attorney's Office | Elected Office | `170010905` | District Attorney - Richmond | token-set | 1.00 |
| `NYC_GOID_000002` | Administration for Children's Services | Mayoral Agency | `170010068` | Administration for Children's Services | exact/alias | 1.00 |
| `NYC_GOID_000135` | Department for the Aging | Mayoral Agency | `170010125` | Department for the Aging | exact/alias | 1.00 |
| `NYC_GOID_000136` | Department of Buildings | Mayoral Agency | `170010810` | Department of Buildings | exact/alias | 1.00 |
| `NYC_GOID_000137` | Department of City Planning | Mayoral Agency | `170010030` | Department of City Planning | exact/alias | 1.00 |
| `NYC_GOID_000138` | Department of Citywide Administrative Services | Mayoral Agency | `170010856` | Department of Citywide Administrative Services | exact/alias | 1.00 |
| `NYC_GOID_000139` | Department of Consumer and Worker Protection | Mayoral Agency | `170010866` | Department of Consumer and Worker Protection | exact/alias | 1.00 |
| `NYC_GOID_000140` | Department of Correction | Mayoral Agency | `170010072` | Department of Correction | exact/alias | 1.00 |
| `NYC_GOID_000141` | Department of Cultural Affairs | Mayoral Agency | `170010126` | Department of Cultural Affairs | exact/alias | 1.00 |
| `NYC_GOID_000142` | Department of Design and Construction | Mayoral Agency | `170010850` | Department of Design and Construction | exact/alias | 1.00 |
| `NYC_GOID_000144` | Department of Environmental Protection | Mayoral Agency | `170010826` | Department of Environmental Protection | exact/alias | 1.00 |
| `NYC_GOID_000145` | Department of Finance | Mayoral Agency | `170010836` | Department of Finance | exact/alias | 1.00 |
| `NYC_GOID_000146` | Department of Health and Mental Hygiene | Mayoral Agency | `170010816` | Department of Health and Mental Hygiene | exact/alias | 1.00 |
| `NYC_GOID_000216` | Department of Housing Preservation and Development | Mayoral Agency | `170010806` | Department of Housing Preservation and Development | exact/alias | 1.00 |
| `NYC_GOID_000148` | Department of Investigation | Mayoral Agency | `170010032` | Department of Investigation | exact/alias | 1.00 |
| `NYC_GOID_000149` | Department of Parks and Recreation | Mayoral Agency | `170010846` | Department of Parks and Recreation | exact/alias | 1.00 |
| `NYC_GOID_000150` | Department of Probation | Mayoral Agency | `170010781` | Department of Probation | exact/alias | 1.00 |
| `NYC_GOID_000151` | Department of Records and Information Services | Mayoral Agency | `170010860` | Department of Records and Information Services | exact/alias | 1.00 |
| `NYC_GOID_000153` | Department of Small Business Services | Mayoral Agency | `170010801` | Department of Small Business Services | exact/alias | 1.00 |
| `NYC_GOID_000154` | Department of Social Services | Mayoral Agency | `170010069` | Department of Social Services | exact/alias | 1.00 |
| `NYC_GOID_000158` | Department of Veterans' Services | Mayoral Agency | `170010063` | Department of Veterans' Services | exact/alias | 1.00 |
| `NYC_GOID_000159` | Department of Youth and Community Development | Mayoral Agency | `170010260` | Department of Youth and Community Development | exact/alias | 1.00 |
| `NYC_GOID_000191` | Fire Department of the City of New York | Mayoral Agency | `170010057` | Fire Department | exact/alias | 1.00 |
| `NYC_GOID_000152` | New York City Department of Sanitation | Mayoral Agency | `170010827` | Department of Sanitation | exact/alias | 1.00 |
| `NYC_GOID_000157` | New York City Department of Transportation | Mayoral Agency | `170010841` | Department of Transportation | exact/alias | 1.00 |
| `NYC_GOID_000315` | New York City Emergency Management | Mayoral Agency | `170010017` | Department of Emergency Management | exact/alias | 1.00 |
| `NYC_GOID_000238` | New York City Law Department | Mayoral Agency | `170010025` | Law Department | exact/alias | 1.00 |
| `NYC_GOID_000389` | New York City Police Department | Mayoral Agency | `170010056` | Police Department | exact/alias | 1.00 |
| `NYC_GOID_000143` | New York City Public Schools | Mayoral Agency | `170010040` | Department of Education | exact/alias | 1.00 |
| `NYC_GOID_000436` | New York City Taxi and Limousine Commission | Mayoral Agency | `170010156` | Taxi & Limousine Commission | exact/alias | 1.00 |
| `NYC_GOID_000346` | Office of Administrative Trials and Hearings | Mayoral Agency | `170011025` | Office of Administrative Trials and Hearings | exact/alias | 1.00 |
| `NYC_GOID_000377` | Office of Payroll Administration | Mayoral Agency | `170010131` | Office of Payroll Administration | exact/alias | 1.00 |
| `NYC_GOID_100021` | Office of the Chief Medical Examiner | Mayoral Agency | `170011026` | Office of Chief Medical Examiner | exact/alias | 1.00 |
| `NYC_GOID_000047` | Center for Innovation through Data Intelligence | Mayoral Office | `170011001` | Center for Innovation through Data Intelligence | exact/alias | 1.00 |
| `NYC_GOID_000265` | Mayor's Office - Correspondence | Mayoral Office | `170100024` | Office of Correspondence | token-set | 1.00 |
| `NYC_GOID_000292` | Mayor's Office - Press Office | Mayoral Office | `170100037` | Press Office | token-set | 1.00 |
| `NYC_GOID_000252` | Mayor's Office for Economic Opportunity | Mayoral Office | `170011040` | Office for Economic Opportunity | token-set | 1.00 |
| `NYC_GOID_000255` | Mayor's Office for International Affairs | Mayoral Office | `170011037` | Office of International Affairs | token-set | 1.00 |
| `NYC_GOID_000284` | Mayor's Office for People with Disabilities | Mayoral Office | `170011016` | Office for People with Disabilities | token-set | 1.00 |
| `NYC_GOID_000385` | Mayor's Office for Prevention of Hate Crimes | Mayoral Office | `170100244` | Office for the Prevention of Hate Crimes | token-set | 1.00 |
| `NYC_GOID_000258` | Mayor's Office of Administrative Services | Mayoral Office | `170100031` | Office of Administrative Services | token-set | 1.00 |
| `NYC_GOID_000260` | Mayor's Office of Appointments | Mayoral Office | `170011017` | Office of Appointments | token-set | 1.00 |
| `NYC_GOID_000262` | Mayor's Office of Climate and Environmental Justice | Mayoral Office | `170011003` | Office of Climate and Environmental Justice | token-set | 1.00 |
| `NYC_GOID_000356` | Mayor's Office of Community Mental Health | Mayoral Office | `170100002` | Office of Community Mental Health | token-set | 1.00 |
| `NYC_GOID_000264` | Mayor's Office of Contract Services | Mayoral Office | `170011020` | Mayor’s Office of Contract Services | exact/alias | 1.00 |
| `NYC_GOID_000266` | Mayor's Office of Criminal Justice | Mayoral Office | `170011021` | Office of Criminal Justice | exact/alias | 1.00 |
| `NYC_GOID_000363` | Mayor's Office of Environmental Coordination | Mayoral Office | `170011011` | Office of Environmental Coordination | exact/alias | 1.00 |
| `NYC_GOID_000364` | Mayor's Office of Environmental Remediation | Mayoral Office | `170011045` | Office of Environmental Remediation | exact/alias | 1.00 |
| `NYC_GOID_000268` | Mayor's Office of Ethnic and Community Media | Mayoral Office | `170100248` | Office of Ethnic and Community Media | token-set | 1.00 |
| `NYC_GOID_000269` | Mayor's Office of Food Policy | Mayoral Office | `170011047` | Office of Food Policy | token-set | 1.00 |
| `NYC_GOID_000217` | Mayor's Office of Housing Recovery Operations | Mayoral Office | `170011014` | Housing Recovery Operations | token-set | 1.00 |
| `NYC_GOID_000270` | Mayor's Office of Immigrant Affairs | Mayoral Office | `170011038` | Office of Immigrant Affairs | token-set | 1.00 |
| `NYC_GOID_000374` | Mayor's Office of Management and Budget | Mayoral Office | `170011030` | Office of Management and Budget | exact/alias | 1.00 |
| `NYC_GOID_000271` | Mayor's Office of Media and Entertainment | Mayoral Office | `170011018` | Office of Media and Entertainment | exact/alias | 1.00 |
| `NYC_GOID_000272` | Mayor's Office of Minority and Women-Owned Business Enterprises | Mayoral Office | `170011029` | Office of Minority and Women-Owned Business Enterprises | token-set | 1.00 |
| `NYC_GOID_000274` | Mayor's Office of Operations | Mayoral Office | `170011019` | Mayor's Office of Operations | exact/alias | 1.00 |
| `NYC_GOID_000275` | Mayor's Office of Pensions and Investments | Mayoral Office | `170100032` | Office of Pensions and Investments | token-set | 1.00 |
| `NYC_GOID_000276` | Mayor's Office of Policy and Planning | Mayoral Office | `170100003` | Office of Policy and Planning | token-set | 1.00 |
| `NYC_GOID_000287` | Mayor's Office of Risk Management and Compliance | Mayoral Office | `170100225` | Office of Risk Management and Compliance | token-set | 1.00 |
| `NYC_GOID_000277` | Mayor's Office of Special Enforcement | Mayoral Office | `170100246` | Office of Special Enforcement | token-set | 1.00 |
| `NYC_GOID_000278` | Mayor's Office of Special Projects and Community Events | Mayoral Office | `170011032` | Office of Special Projects and Community Events | token-set | 1.00 |
| `NYC_GOID_000279` | Mayor's Office of Sports, Wellness and Recreation | Mayoral Office | `170100241` | Office of Sports, Wellness and Recreation | token-set | 1.00 |
| `NYC_GOID_000280` | Mayor's Office of Strategic Partnerships | Mayoral Office | `170100029` | Office of Strategic Partnerships | token-set | 1.00 |
| `NYC_GOID_000281` | Mayor's Office of Talent and Workforce Development | Mayoral Office | `170011049` | Office of Workforce Development | curated | 1.00 |
| `NYC_GOID_000283` | Mayor's Office of Youth Employment | Mayoral Office | `170100228` | Office of Youth Employment | token-set | 1.00 |
| `NYC_GOID_000253` | Mayor's Office to End Domestic and Gender-Based Violence | Mayoral Office | `170011009` | Office to End Domestic Violence and Gender-Based Violence | token-set | 1.00 |
| `NYC_GOID_100018` | Mayor's Office to Prevent Gun Violence | Mayoral Office | `170100245` | Office to Prevent Gun Violence | token-set | 1.00 |
| `NYC_GOID_000286` | Mayor's Office to Protect Tenants | Mayoral Office | `170100020` | Office to Protect Tenants | token-set | 1.00 |
| `NYC_GOID_000312` | New York City Children's Cabinet | Mayoral Office | `170100014` | Children's Cabinet | exact/alias | 1.00 |
| `NYC_GOID_000468` | New York City Young Men's Initiative | Mayoral Office | `170011024` | Young Men’s Initiative | exact/alias | 1.00 |
| `NYC_GOID_000349` | Office of Capital Project Development | Mayoral Office | `170100242` | Office of Capital Project Development | exact/alias | 1.00 |
| `NYC_GOID_000226` | Office of Intergovernmental Affairs | Mayoral Office | `170011039` | Office of Intergovernmental Affairs | exact/alias | 1.00 |
| `NYC_GOID_000371` | Office of Labor Relations | Mayoral Office | `170011028` | Office of Labor Relations | exact/alias | 1.00 |
| `NYC_GOID_000380` | Office of Scheduling and Executive Operations | Mayoral Office | `170100022` | Scheduling and Executive Operations | exact/alias | 1.00 |
| `NYC_GOID_000382` | Office of Technology and Innovation | Mayoral Office | `170010858` | Office of Technology and Innovation | exact/alias | 1.00 |
| `NYC_GOID_000344` | Office of the Administrative Justice Coordinator | Mayoral Office | `170019001` | Office of Administrative Justice Coordinator | exact/alias | 1.00 |
| `NYC_GOID_000038` | Brooklyn Public Library | Nonprofit Organization | `170010038` | Brooklyn Public Library | exact/alias | 1.00 |
| `NYC_GOID_000202` | Gracie Mansion Conservancy | Nonprofit Organization | `170100018` | Gracie Mansion | curated | 1.00 |
| `NYC_GOID_000208` | GrowNYC | Nonprofit Organization | `132765465` | GrowNYC | exact/alias | 1.00 |
| `NYC_GOID_000248` | Mayor's Fund to Advance New York City | Nonprofit Organization | `170011036` | Mayor's Fund to Advance New York City | exact/alias | 1.00 |
| `NYC_GOID_000310` | New York City Tourism + Conventions | Nonprofit Organization | `170019006` | NYC & Company | exact/alias | 1.00 |
| `NYC_GOID_000335` | New York Public Library | Nonprofit Organization | `170010037` | New York Public Library | exact/alias | 1.00 |
| `NYC_GOID_000402` | Queens Public Library | Nonprofit Organization | `170010039` | Queens Public Library | exact/alias | 1.00 |
| `NYC_GOID_000022` | Board of Education Retirement System | Pension Fund | `170019002` | Board of Education Retirement System | exact/alias | 1.00 |
| `NYC_GOID_000192` | Fire Department Pension Fund and Related Funds | Pension Fund | `170011012` | Fire Department Pension Fund & Related Funds | exact/alias | 1.00 |
| `NYC_GOID_000316` | New York City Employee Retirement System | Pension Fund | `170019003` | Employees Retirement System | exact/alias | 1.00 |
| `NYC_GOID_000390` | New York City Police Pension Fund | Pension Fund | `170019008` | Police Pension Fund | exact/alias | 1.00 |
| `NYC_GOID_000437` | Teachers' Retirement System of City of New York | Pension Fund | `170019014` | Teachers' Retirement System | exact/alias | 1.00 |
| `NYC_GOID_000034` | Brooklyn Bridge Park Corporation | Public Benefit or Development Organization | `272846763` | Brooklyn Bridge Park Corporation | exact/alias | 1.00 |
| `NYC_GOID_000037` | Brooklyn Navy Yard Development Corporation | Public Benefit or Development Organization | `112137138` | Brooklyn Navy Yard Development Corporation | exact/alias | 1.00 |
| `NYC_GOID_000100` | City University Construction Fund | Public Benefit or Development Organization | `170010043` | City University Construction Fund | exact/alias | 1.00 |
| `NYC_GOID_000177` | Economic Development Corporation | Public Benefit or Development Organization | `170010998` | Economic Development Corporation | exact/alias | 1.00 |
| `NYC_GOID_000181` | Educational Construction Fund | Public Benefit or Development Organization | `170011010` | Educational Construction Fund | exact/alias | 1.00 |
| `NYC_GOID_000215` | Housing Development Corporation | Public Benefit or Development Organization | `170019004` | Housing Development Corporation | exact/alias | 1.00 |
| `NYC_GOID_000218` | Hudson River Park Trust | Public Benefit or Development Organization | `61546019` | Hudson River Park Trust | exact/alias | 1.00 |
| `NYC_GOID_000220` | Hudson Yards Infrastructure Corporation | Public Benefit or Development Organization | `170019029` | Hudson Yards Infrastructure Corporation | exact/alias | 1.00 |
| `NYC_GOID_000241` | Lower Manhattan Development Corporation | Public Benefit or Development Organization | `170019032` | Lower Manhattan Development Corporation | exact/alias | 1.00 |
| `NYC_GOID_000476` | Metropolitan Transportation Authority | Public Benefit or Development Organization | `170020045` | Metropolitan Transportation Authority | exact/alias | 1.00 |
| `NYC_GOID_000318` | NYC Health + Hospitals | Public Benefit or Development Organization | `170010819` | Health and Hospitals Corporation | token-set | 1.00 |
| `NYC_GOID_000319` | New York City Housing Authority | Public Benefit or Development Organization | `170020034` | NYC Housing Authority | exact/alias | 1.00 |
| `NYC_GOID_000308` | New York City Municipal Water Finance Authority | Public Benefit or Development Organization | `170019017` | NYC Municipal Water Finance Authority | exact/alias | 1.00 |
| `NYC_GOID_000331` | New York City Transitional Finance Authority | Public Benefit or Development Organization | `170019005` | New York City Transitional Finance Authority | exact/alias | 1.00 |
| `NYC_GOID_000459` | New York City Water Board | Public Benefit or Development Organization | `170011044` | New York City Water Board | exact/alias | 1.00 |
| `NYC_GOID_000414` | Roosevelt Island Operating Corporation | Public Benefit or Development Organization | `170020087` | Roosevelt Island Operating Corporation | exact/alias | 1.00 |
| `NYC_GOID_000415` | Sales Tax Asset Receivable Corporation | Public Benefit or Development Organization | `170019036` | Sales Tax Asset Receivable Corporation | exact/alias | 1.00 |
| `NYC_GOID_000416` | School Construction Authority | Public Benefit or Development Organization | `170019011` | School Construction Authority | exact/alias | 1.00 |
| `NYC_GOID_000445` | Tobacco Settlement Asset Securitization Corporation | Public Benefit or Development Organization | `170019037` | TSASC, Inc | exact/alias | 1.00 |
| `NYC_GOID_000449` | Trust for Governors Island | Public Benefit or Development Organization | `272683349` | Trust for Governors Island | exact/alias | 1.00 |
| `NYC_GOID_000452` | United Nations Development Corporation | Public Benefit or Development Organization | `132626199` | United Nations Development Corporation | exact/alias | 1.00 |
| `NYC_GOID_000395` | Bronx County Public Administrator | State Government Agency | `170010942` | Public Administrator - Bronx | token-set | 1.00 |
| `NYC_GOID_000099` | City University of New York | State Government Agency | `170010042` | City University of New York | exact/alias | 1.00 |
| `NYC_GOID_000234` | Kings County Public Administrator | State Government Agency | `170010943` | Public Administrator- Brooklyn | token-set | 1.00 |
| `NYC_GOID_000334` | New York County Public Administrator | State Government Agency | `170019009` | Public Administrator | token-set | 1.00 |
| `NYC_GOID_000401` | Public Administrator of Queens County | State Government Agency | `170010944` | Public Administrator - Queens | token-set | 1.00 |
| `NYC_GOID_000412` | Richmond County Public Administrator | State Government Agency | `170010945` | Public Administrator - Richmond | token-set | 1.00 |

## Reviewed and REJECTED - 7

Human-refused on 2026-07-30 and stored so a rebuild never re-suggests them. Three different bodies all scored 0.7+ against our single Office of Workforce Development.

| OTI record_id | OTI name | type | our id | our name | tier | score |
|---|---|---|---|---|---|---|
| `NYC_GOID_000116` | Community Action Board at the NYC Department of Youth and Community Development | Advisory or Regulatory Organization | `170010260` | Department of Youth and Community Development | rejected | 0.73 |
| `NYC_GOID_000320` | New York City Housing Authority Board | Advisory or Regulatory Organization | `170020034` | NYC Housing Authority | rejected | 0.72 |
| `NYC_GOID_000461` | Workforce Development Board | Advisory or Regulatory Organization | `170011049` | Office of Workforce Development | rejected | 0.72 |
| `NYC_GOID_000462` | Workforce Development Council | Advisory or Regulatory Organization | `170011049` | Office of Workforce Development | rejected | 0.70 |
| `NYC_GOID_100004` | NYC HER Future | Division | `222879323` | NJ Future | rejected | 0.70 |
| `NYC_GOID_100037` | Deputy Mayor for Community Safety | Mayoral Office | `170100243` | Deputy Mayor for Public Safety | rejected | 0.79 |
| `NYC_GOID_000163` | Deputy Mayor for Operations | Mayoral Office | `170011019` | Mayor's Office of Operations | rejected | 0.69 |

## No match - 126

Genuinely absent from our directory. The nonprofits are largely Cultural Institutions Group members - a scope decision rather than a data gap.

| OTI record_id | OTI name | type | acronym | reports_to |
|---|---|---|---|---|
| `NYC_GOID_000008` | Advisory Council for the NYC Civil Court Housing Part | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000009` | Advisory Council on Procurement Lobbying | Advisory or Regulatory Organization | ACPL |  |
| `NYC_GOID_100013` | Archival Review Board | Advisory or Regulatory Organization | ARB |  |
| `NYC_GOID_000014` | Archives, Reference and Research Advisory Board | Advisory or Regulatory Organization | ARRAB |  |
| `NYC_GOID_000017` | Audit Committee | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000018` | Banking Commission | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000024` | Board of Health | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_100001` | Borough Boards | Advisory or Regulatory Organization |  | Office of the Borough President of The Bronx;Office of the Borough President of Brooklyn;Office of the Borough President of Manhattan;Office of the Borough President of Queens;Office of the Borough President of Staten Island |
| `NYC_GOID_000050` | Charter Revision Commission | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000113` | Commission on Racial Equity | Advisory or Regulatory Organization | CORE | Deputy Mayor for Economic Justice |
| `NYC_GOID_100016` | Cultural Affairs Advisory Commission | Advisory or Regulatory Organization | CAAC |  |
| `NYC_GOID_000174` | Domestic Violence Fatality Review Committee | Advisory or Regulatory Organization | FRC |  |
| `NYC_GOID_000179` | Economic Development Corporation Life Sciences Advisory Council | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000182` | Environmental Control Board | Advisory or Regulatory Organization | ECB |  |
| `NYC_GOID_000201` | Get Stuff Built Advisory Board | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000205` | Green Economy Advisory Council | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000213` | HIV Planning Council | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000214` | HIV/AIDS Services Advisory Board | Advisory or Regulatory Organization | HASA |  |
| `NYC_GOID_000233` | Juvenile Justice Advisory Board | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000309` | MWBE Advisory Board | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000245` | Mayor's Advisory Committee on the Judiciary | Advisory or Regulatory Organization | MACJ | Chief Counsel to the Mayor and City Hall |
| `NYC_GOID_000314` | New York City Districting Commission | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000324` | New York City Panel on Climate Change | Advisory or Regulatory Organization | NPCC |  |
| `NYC_GOID_000330` | New York City Transit Riders Council | Advisory or Regulatory Organization | NYCTRC |  |
| `NYC_GOID_000332` | New York City Watershed Protection and Partnership Council | Advisory or Regulatory Organization | WPPC |  |
| `NYC_GOID_000338` | Nonprofit Advisory Council | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000387` | Panel on Educational Policy | Advisory or Regulatory Organization | PEP |  |
| `NYC_GOID_000388` | Pay Equity Cabinet | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000418` | Senior Advisory Council | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000428` | Street Harassment Prevention Advisory Board | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000433` | Taskforce on Racial Inclusion and Equity | Advisory or Regulatory Organization | TRIE |  |
| `NYC_GOID_000443` | Three Quarter Housing Task Force | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_000456` | Veterans Advisory Board | Advisory or Regulatory Organization | VAB |  |
| `NYC_GOID_000458` | Voter Assistance Advisory Committee | Advisory or Regulatory Organization | VAAC |  |
| `NYC_GOID_100026` | Youth Board | Advisory or Regulatory Organization |  |  |
| `NYC_GOID_100006` | Mayor's Office of Urban Agriculture | Division | MOUA | Mayor's Office of Climate and Environmental Justice |
| `NYC_GOID_000355` | Office of Community Hiring | Division |  | Mayor's Office of Talent and Workforce Development |
| `NYC_GOID_000128` | Chief Counsel to the Mayor and City Hall | Mayoral Office |  | Office of the Mayor |
| `NYC_GOID_000246` | Chief of Staff to the Mayor | Mayoral Office |  | Mayor |
| `NYC_GOID_100033` | Deputy Mayor for Economic Justice | Mayoral Office |  | Office of the Mayor |
| `NYC_GOID_000161` | Deputy Mayor for Health and Human Services | Mayoral Office | DMHHS | Office of the Mayor |
| `NYC_GOID_100032` | Deputy Mayor for Housing and Planning | Mayoral Office |  | Office of the Mayor |
| `NYC_GOID_000193` | First Deputy Mayor | Mayoral Office | FDM | Office of the Mayor |
| `NYC_GOID_000244` | Mayor's Advance Team | Mayoral Office |  | Deputy Mayor for Administration and Chief of Staff |
| `NYC_GOID_100007` | Mayor's Office - Director of Communications | Mayoral Office |  | Deputy Mayor for Communications |
| `NYC_GOID_100035` | Mayor's Office - Senior Advisor for Policy and Strategy | Mayoral Office |  |  |
| `NYC_GOID_000351` | Mayor's Office for Childcare and Early Childhood Education | Mayoral Office | OCCECE | First Deputy Mayor |
| `NYC_GOID_000257` | Mayor's Office for Nonprofit Services | Mayoral Office | MONS | Deputy Mayor for Operations |
| `NYC_GOID_000261` | Mayor's Office of Citywide Events Coordination and Management | Mayoral Office | CECM | Chief of Staff |
| `NYC_GOID_100040` | Mayor's Office of Community Safety | Mayoral Office |  |  |
| `NYC_GOID_100039` | Mayor's Office of Deed Theft Prevention | Mayoral Office |  |  |
| `NYC_GOID_000267` | Mayor's Office of Equity and Racial Justice | Mayoral Office | MOERJ | Deputy Mayor for Strategic Initiatives |
| `NYC_GOID_100019` | Mayor's Office of Faith-Based and Community Partnerships | Mayoral Office | OFCP | Mayor's Office of Mass Engagement |
| `NYC_GOID_100038` | Mayor's Office of LGBTQIA+ Affairs | Mayoral Office |  |  |
| `NYC_GOID_100034` | Mayor's Office of Mass Engagement | Mayoral Office |  |  |
| `NYC_GOID_000306` | Mayor's Office of Municipal Services Assessment | Mayoral Office | MSA | Deputy Mayor for Public Safety |
| `NYC_GOID_100031` | Mayor's Office of Rodent Mitigation | Mayoral Office |  |  |
| `NYC_GOID_000298` | Mayor's Office of the Utility Consumer Advocate | Mayoral Office |  |  |
| `NYC_GOID_100036` | Mayor's Office to Combat Antisemitism | Mayoral Office |  |  |
| `NYC_GOID_000303` | Municipal Division of Transitional Services | Mayoral Office |  |  |
| `NYC_GOID_100029` | Office Conversion Accelerator | Mayoral Office |  |  |
| `NYC_GOID_100008` | Office of Creative Communications | Mayoral Office |  | Deputy Mayor for Communications |
| `NYC_GOID_000367` | Office of Healthcare Accountability | Mayoral Office |  |  |
| `NYC_GOID_000399` | Office of the Public Realm | Mayoral Office |  |  |
| `NYC_GOID_000059` | American Museum of Natural History | Nonprofit Organization | AMNH |  |
| `NYC_GOID_000012` | Animal Care Centers of NYC | Nonprofit Organization | ACC |  |
| `NYC_GOID_000060` | Bronx County Historical Society | Nonprofit Organization |  |  |
| `NYC_GOID_000061` | Bronx Museum of the Arts | Nonprofit Organization |  |  |
| `NYC_GOID_000062` | Brooklyn Academy of Music | Nonprofit Organization | BAM |  |
| `NYC_GOID_000063` | Brooklyn Botanic Garden | Nonprofit Organization | BBG |  |
| `NYC_GOID_000064` | Brooklyn Children's Museum | Nonprofit Organization | BCM |  |
| `NYC_GOID_000065` | Brooklyn Museum | Nonprofit Organization |  |  |
| `NYC_GOID_000066` | Carnegie Hall | Nonprofit Organization |  |  |
| `NYC_GOID_100015` | Center for Brooklyn History | Nonprofit Organization | CBH | Brooklyn Public Library |
| `NYC_GOID_000048` | Central Park Conservancy | Nonprofit Organization |  |  |
| `NYC_GOID_000127` | Council for Airport Opportunity | Nonprofit Organization | CAO |  |
| `NYC_GOID_000067` | El Museo del Barrio | Nonprofit Organization |  |  |
| `NYC_GOID_000068` | Flushing Council on Culture and the Arts / Flushing Town Hall | Nonprofit Organization |  |  |
| `NYC_GOID_000194` | Flushing Meadows Corona Park Alliance | Nonprofit Organization |  |  |
| `NYC_GOID_000198` | Fund for Public Schools | Nonprofit Organization |  |  |
| `NYC_GOID_000206` | Greenbelt Conservancy | Nonprofit Organization |  |  |
| `NYC_GOID_000230` | Jamaica Bay - Rockaway Parks Conservancy, Inc. | Nonprofit Organization | JBRPC |  |
| `NYC_GOID_000069` | Jamaica Center for Arts and Learning | Nonprofit Organization | JCAL |  |
| `NYC_GOID_000070` | Jazz at Lincoln Center | Nonprofit Organization |  |  |
| `NYC_GOID_000071` | Lincoln Center Theater | Nonprofit Organization | LCT |  |
| `NYC_GOID_000072` | Metropolitan Museum of Art | Nonprofit Organization |  |  |
| `NYC_GOID_000081` | MoMA PS1 | Nonprofit Organization | MOMA PS1 |  |
| `NYC_GOID_000074` | Museum of Jewish Heritage | Nonprofit Organization |  |  |
| `NYC_GOID_000075` | Museum of Modern Art | Nonprofit Organization | MoMA |  |
| `NYC_GOID_000073` | Museum of the City of New York | Nonprofit Organization | MCNY |  |
| `NYC_GOID_000076` | Museum of the Moving Image | Nonprofit Organization | MoMI |  |
| `NYC_GOID_000464` | National September 11 Memorial and Museum | Nonprofit Organization |  |  |
| `NYC_GOID_000077` | New York Botanical Garden | Nonprofit Organization | NYBG |  |
| `NYC_GOID_000078` | New York City Ballet | Nonprofit Organization |  |  |
| `NYC_GOID_000079` | New York City Center | Nonprofit Organization |  |  |
| `NYC_GOID_000327` | New York City School Support Services | Nonprofit Organization | NYCSSS |  |
| `NYC_GOID_000080` | New York Hall of Science | Nonprofit Organization | NYSCI |  |
| `NYC_GOID_000465` | Perelman Performing Arts Center | Nonprofit Organization | PACNYC |  |
| `NYC_GOID_000394` | Prospect Park Alliance | Nonprofit Organization |  |  |
| `NYC_GOID_000082` | Public Theater | Nonprofit Organization |  |  |
| `NYC_GOID_000083` | Queens Botanical Garden | Nonprofit Organization | QBG |  |
| `NYC_GOID_000084` | Queens Museum | Nonprofit Organization |  |  |
| `NYC_GOID_000085` | Queens Theatre in the Park | Nonprofit Organization |  |  |
| `NYC_GOID_000405` | Randall's Island Park Alliance | Nonprofit Organization | RIPA |  |
| `NYC_GOID_000086` | Snug Harbor Cultural Center and Botanical Garden | Nonprofit Organization |  |  |
| `NYC_GOID_000087` | Staten Island Children's Museum | Nonprofit Organization |  |  |
| `NYC_GOID_000088` | Staten Island Historical Society | Nonprofit Organization |  |  |
| `NYC_GOID_000089` | Staten Island Museum | Nonprofit Organization |  |  |
| `NYC_GOID_000090` | Staten Island Zoological Society | Nonprofit Organization |  |  |
| `NYC_GOID_000091` | Studio Museum in Harlem | Nonprofit Organization |  |  |
| `NYC_GOID_000092` | Wave Hill | Nonprofit Organization |  |  |
| `NYC_GOID_000093` | Weeksville Heritage Center | Nonprofit Organization |  |  |
| `NYC_GOID_000094` | Wildlife Conservation Society | Nonprofit Organization | WCS |  |
| `NYC_GOID_000130` | Cultural Institutions Retirement System | Pension Fund | CIRS |  |
| `NYC_GOID_100014` | Build NYC Resource Corporation | Public Benefit or Development Organization |  |  |
| `NYC_GOID_000045` | Catskill Watershed Corporation | Public Benefit or Development Organization | CWC |  |
| `NYC_GOID_000125` | Convention Center Development Corporation | Public Benefit or Development Organization | CCDC |  |
| `NYC_GOID_000126` | Convention Center Operating Corporation (Javits) | Public Benefit or Development Organization | NYCCOC |  |
| `NYC_GOID_000196` | Forest Park Trust | Public Benefit or Development Organization |  |  |
| `NYC_GOID_000224` | Industrial Development Agency | Public Benefit or Development Organization | NYCIDA |  |
| `NYC_GOID_000235` | Land Development Corporation | Public Benefit or Development Organization | NYCLDC |  |
| `NYC_GOID_000325` | New York City Public Housing Preservation Trust | Public Benefit or Development Organization |  |  |
| `NYC_GOID_000326` | New York City School Bus Umbrella Services, Inc. | Public Benefit or Development Organization |  |  |
| `NYC_GOID_000391` | Primary Care Development Corporation | Public Benefit or Development Organization | PCDC |  |
| `NYC_GOID_000410` | Residential Mortgage Insurance Corporation | Public Benefit or Development Organization | REMIC |  |
| `NYC_GOID_000448` | Trust for Cultural Resources | Public Benefit or Development Organization | TCR |  |

