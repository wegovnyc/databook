# OTI agency registry (`t3jq-9nkf`) -- adoption review

What the adoption brought across, and every disagreement it recorded instead of
applying. Regenerate with:

    docker compose exec -T api python adopt_nyc_orgs.py --report > \
        docs/nyc-org-adoption-review.md

OTI's attributes are additive: they live in `nyc_org_enrichment`, and
`wegov_orgs` keeps its own `name`, `type` and parent. Where the two disagree the
row below is the decision waiting to be made -- nothing here has been applied to
`wegov_orgs`.


## Where things stand

| | |
|---|---:|
| `wegov_orgs` rows | 1240 |
| live (not retired) | 1238 |
| created from an OTI record | 134 |
| OTI records with an enrichment row | 306 |
| **name disagreements** | **82** |
| **type disagreements** | **0** |
| **parent disagreements** | **10** |
| imported with a low-confidence type | 0 |

## New attributes now held (additively, in `nyc_org_enrichment`)

| attribute | populated |
|---|---:|
| `acronym` | 193 |
| `alternate_or_former_names` | 47 |
| `principal_officer_full_name` | 238 |
| `principal_officer_title` | 248 |
| `principal_officer_contact` | 147 |
| `reports_to` | 132 |
| `in_org_chart = true` | 145 |

## Retired duplicates

Additive, never deleted -- `retired_at` + `merged_into`, so the merge is reversible.

| id | name | was typed | merged into |
|---|---|---|---|
| `170020048` | Public Design Commission | State Agency | `170011008` Public Design Commission |
| `170100011` | Commission on Gender Equality | City Agency | `170011004` Commission on Gender Equity |

## Types, taken from OTI verbatim

OTI's `organization_type` is adopted as-is -- no mapping, nothing guessed. Our own `Nonprofit` was renamed to OTI's `Nonprofit Organization` throughout, including rows OTI does not cover.

⚠ `Nonprofit Organization` is deliberately absent from `/get/orgs/directory`'s type filter, so those rows exist without entering a directory of government.

| type | orgs in the registry | of which imported |
|---|---:|---:|
| Mayoral Office | 72 | 29 |
| Advisory or Regulatory Organization | 68 | 40 |
| Nonprofit Organization | 56 | 49 |
| Public Benefit or Development Organization | 33 | 12 |
| Mayoral Agency | 32 | 0 |
| Division | 19 | 3 |
| Elected Office | 14 | 0 |
| Pension Fund | 6 | 1 |
| State Government Agency | 6 | 0 |

## Displayed names -- 82

The site shows OTI's official name; `name` is unchanged, so every `/o/{id}-{slug}` URL stays byte-identical and the `contracts.agency` join keeps working.

| id | shown (OTI) | stored `name` (URL + join key) |
|---|---|---|
| `170010942` | Bronx County Public Administrator | Public Administrator - Bronx |
| `170010902` | Bronx District Attorney's Office | District Attorney - Bronx |
| `170010903` | Brooklyn District Attorney's Office | District Attorney - Kings |
| `170010226` | City Commission on Human Rights | Commission on Human Rights |
| `170100033` | Cyber Command | NYC Cyber Command |
| `170010057` | Fire Department of the City of New York | Fire Department |
| `170100018` | Gracie Mansion Conservancy | Gracie Mansion |
| `170010943` | Kings County Public Administrator | Public Administrator- Brooklyn |
| `170010901` | Manhattan District Attorney's Office | District Attorney - New York |
| `170100024` | Mayor's Office - Correspondence | Office of Correspondence |
| `170100037` | Mayor's Office - Press Office | Press Office |
| `170011040` | Mayor's Office for Economic Opportunity | Office for Economic Opportunity |
| `170011037` | Mayor's Office for International Affairs | Office of International Affairs |
| `170011016` | Mayor's Office for People with Disabilities | Office for People with Disabilities |
| `170100244` | Mayor's Office for Prevention of Hate Crimes | Office for the Prevention of Hate Crimes |
| `170100031` | Mayor's Office of Administrative Services | Office of Administrative Services |
| `170100224` | Mayor's Office of Animal Welfare | Office of Animal Welfare |
| `170011017` | Mayor's Office of Appointments | Office of Appointments |
| `170011003` | Mayor's Office of Climate and Environmental Justice | Office of Climate and Environmental Justice |
| `170100002` | Mayor's Office of Community Mental Health | Office of Community Mental Health |
| `170011021` | Mayor's Office of Criminal Justice | Office of Criminal Justice |
| `170011011` | Mayor's Office of Environmental Coordination | Office of Environmental Coordination |
| `170011045` | Mayor's Office of Environmental Remediation | Office of Environmental Remediation |
| `170100248` | Mayor's Office of Ethnic and Community Media | Office of Ethnic and Community Media |
| `170011047` | Mayor's Office of Food Policy | Office of Food Policy |
| `170011014` | Mayor's Office of Housing Recovery Operations | Housing Recovery Operations |
| `170011038` | Mayor's Office of Immigrant Affairs | Office of Immigrant Affairs |
| `170011030` | Mayor's Office of Management and Budget | Office of Management and Budget |
| `170011018` | Mayor's Office of Media and Entertainment | Office of Media and Entertainment |
| `170011029` | Mayor's Office of Minority and Women-Owned Business Enterprises | Office of Minority and Women-Owned Business Enterprises |
| `170100032` | Mayor's Office of Pensions and Investments | Office of Pensions and Investments |
| `170100003` | Mayor's Office of Policy and Planning | Office of Policy and Planning |
| `170100225` | Mayor's Office of Risk Management and Compliance | Office of Risk Management and Compliance |
| `170100246` | Mayor's Office of Special Enforcement | Office of Special Enforcement |
| `170011032` | Mayor's Office of Special Projects and Community Events | Office of Special Projects and Community Events |
| `170100241` | Mayor's Office of Sports, Wellness and Recreation | Office of Sports, Wellness and Recreation |
| `170100029` | Mayor's Office of Strategic Partnerships | Office of Strategic Partnerships |
| `170011049` | Mayor's Office of Talent and Workforce Development | Office of Workforce Development |
| `170100228` | Mayor's Office of Youth Employment | Office of Youth Employment |
| `170011009` | Mayor's Office to End Domestic and Gender-Based Violence | Office to End Domestic Violence and Gender-Based Violence |
| `170100245` | Mayor's Office to Prevent Gun Violence | Office to Prevent Gun Violence |
| `170100020` | Mayor's Office to Protect Tenants | Office to Protect Tenants |
| `170100009` | Mayor's Public Engagement Unit | Public Engagement Unit |
| `170010819` | NYC Health + Hospitals | Health and Hospitals Corporation |
| `170100005` | NYC311 | NYC 311 |
| `170100014` | New York City Children's Cabinet | Children's Cabinet |
| `170010102` | New York City Council | City Council |
| `170010827` | New York City Department of Sanitation | Department of Sanitation |
| `170010841` | New York City Department of Transportation | Department of Transportation |
| `170010017` | New York City Emergency Management | Department of Emergency Management |
| `170019003` | New York City Employee Retirement System | Employees Retirement System |
| `170020034` | New York City Housing Authority | NYC Housing Authority |
| `170010025` | New York City Law Department | Law Department |
| `170019017` | New York City Municipal Water Finance Authority | NYC Municipal Water Finance Authority |
| `170010008` | New York City Office of the Actuary | Office of the Actuary |
| `170010056` | New York City Police Department | Police Department |
| `170019008` | New York City Police Pension Fund | Police Pension Fund |
| `170010040` | New York City Public Schools | Department of Education |
| `170010156` | New York City Taxi and Limousine Commission | Taxi & Limousine Commission |
| `170019006` | New York City Tourism + Conventions | NYC & Company |
| `170011024` | New York City Young Men's Initiative | Young Men’s Initiative |
| `170019009` | New York County Public Administrator | Public Administrator |
| `170100022` | Office of Scheduling and Executive Operations | Scheduling and Executive Operations |
| `170019001` | Office of the Administrative Justice Coordinator | Office of Administrative Justice Coordinator |
| `170010012` | Office of the Borough President of Brooklyn | Brooklyn Borough President |
| `170010010` | Office of the Borough President of Manhattan | Manhattan Borough President |
| `170010013` | Office of the Borough President of Queens | Queens Borough President |
| `170010014` | Office of the Borough President of Staten Island | Staten Island Borough President |
| `170010011` | Office of the Borough President of The Bronx | Bronx Borough President |
| `170011026` | Office of the Chief Medical Examiner | Office of Chief Medical Examiner |
| `170010103` | Office of the City Clerk | City Clerk |
| `170010002` | Office of the Mayor | Mayor's Office |
| `170010015` | Office of the New York City Comptroller | Office of the Comptroller |
| `170010101` | Office of the Public Advocate | Public Advocate |
| `170010906` | Office of the Special Narcotics Prosecutor | Office of Prosecutor & Special Narcotics |
| `170010944` | Public Administrator of Queens County | Public Administrator - Queens |
| `170010904` | Queens District Attorney's Office | District Attorney - Queens |
| `170010945` | Richmond County Public Administrator | Public Administrator - Richmond |
| `170011015` | Special Commissioner of Investigation for the New York City School District | Special Commissioner of Investigation for the NYC School District |
| `170010905` | Staten Island District Attorney's Office | District Attorney - Richmond |
| `170019014` | Teachers' Retirement System of City of New York | Teachers' Retirement System |
| `170019037` | Tobacco Settlement Asset Securitization Corporation | TSASC, Inc |

## Type disagreements -- 0

OTI's `organization_type` maps to a different `wegov_orgs.type` than the one we hold. Ours is unchanged.

| our id | OTI record | OTI name | OTI type | type that implies | our name |
|---|---|---|---|---|---|

## Parent disagreements -- 6

⚠ OTI's `reports_to` is free text that does not always match OTI's own `name` field, so some of these are source noise rather than a real disagreement.

| our id | OTI name | OTI reports_to | our parent |
|---|---|---|---|
| `170019004` | Housing Development Corporation | Deputy Mayor of Housing Economic and Workforce Development | Chief Housing Officer |
| `170100024` | Mayor's Office - Correspondence | Deputy Mayor for Administration and Chief of Staff | Chief of Staff |
| `170100037` | Mayor's Office - Press Office | Deputy Mayor for Communications | Director of Communications |
| `170100031` | Mayor's Office of Administrative Services | Deputy Mayor for Administration and Chief of Staff | Chief of Staff |
| `170100224` | Mayor's Office of Animal Welfare | Mayor's Community Affairs Unit | Community Affairs Unit |
| `170100022` | Office of Scheduling and Executive Operations | Deputy Mayor for Administration and Chief of Staff | Chief of Staff |

## Name disagreements -- 82

Mostly OTI's longer official forms (`New York City X` vs our `X`). Adopting a name changes URLs, so none were applied.

| our id | OTI record | OTI name | our name |
|---|---|---|---|
| `170010942` | `NYC_GOID_000395` | Bronx County Public Administrator | Public Administrator - Bronx |
| `170010902` | `NYC_GOID_000168` | Bronx District Attorney's Office | District Attorney - Bronx |
| `170010903` | `NYC_GOID_000169` | Brooklyn District Attorney's Office | District Attorney - Kings |
| `170010226` | `NYC_GOID_000096` | City Commission on Human Rights | Commission on Human Rights |
| `170100033` | `NYC_GOID_100010` | Cyber Command | NYC Cyber Command |
| `170010057` | `NYC_GOID_000191` | Fire Department of the City of New York | Fire Department |
| `170100018` | `NYC_GOID_000202` | Gracie Mansion Conservancy | Gracie Mansion |
| `170010943` | `NYC_GOID_000234` | Kings County Public Administrator | Public Administrator- Brooklyn |
| `170010901` | `NYC_GOID_000170` | Manhattan District Attorney's Office | District Attorney - New York |
| `170100024` | `NYC_GOID_000265` | Mayor's Office - Correspondence | Office of Correspondence |
| `170100037` | `NYC_GOID_000292` | Mayor's Office - Press Office | Press Office |
| `170011040` | `NYC_GOID_000252` | Mayor's Office for Economic Opportunity | Office for Economic Opportunity |
| `170011037` | `NYC_GOID_000255` | Mayor's Office for International Affairs | Office of International Affairs |
| `170011016` | `NYC_GOID_000284` | Mayor's Office for People with Disabilities | Office for People with Disabilities |
| `170100244` | `NYC_GOID_000385` | Mayor's Office for Prevention of Hate Crimes | Office for the Prevention of Hate Crimes |
| `170100031` | `NYC_GOID_000258` | Mayor's Office of Administrative Services | Office of Administrative Services |
| `170100224` | `NYC_GOID_000259` | Mayor's Office of Animal Welfare | Office of Animal Welfare |
| `170011017` | `NYC_GOID_000260` | Mayor's Office of Appointments | Office of Appointments |
| `170011003` | `NYC_GOID_000262` | Mayor's Office of Climate and Environmental Justice | Office of Climate and Environmental Justice |
| `170100002` | `NYC_GOID_000356` | Mayor's Office of Community Mental Health | Office of Community Mental Health |
| `170011021` | `NYC_GOID_000266` | Mayor's Office of Criminal Justice | Office of Criminal Justice |
| `170011011` | `NYC_GOID_000363` | Mayor's Office of Environmental Coordination | Office of Environmental Coordination |
| `170011045` | `NYC_GOID_000364` | Mayor's Office of Environmental Remediation | Office of Environmental Remediation |
| `170100248` | `NYC_GOID_000268` | Mayor's Office of Ethnic and Community Media | Office of Ethnic and Community Media |
| `170011047` | `NYC_GOID_000269` | Mayor's Office of Food Policy | Office of Food Policy |
| `170011014` | `NYC_GOID_000217` | Mayor's Office of Housing Recovery Operations | Housing Recovery Operations |
| `170011038` | `NYC_GOID_000270` | Mayor's Office of Immigrant Affairs | Office of Immigrant Affairs |
| `170011030` | `NYC_GOID_000374` | Mayor's Office of Management and Budget | Office of Management and Budget |
| `170011018` | `NYC_GOID_000271` | Mayor's Office of Media and Entertainment | Office of Media and Entertainment |
| `170011029` | `NYC_GOID_000272` | Mayor's Office of Minority and Women-Owned Business Enterprises | Office of Minority and Women-Owned Business Enterprises |
| `170100032` | `NYC_GOID_000275` | Mayor's Office of Pensions and Investments | Office of Pensions and Investments |
| `170100003` | `NYC_GOID_000276` | Mayor's Office of Policy and Planning | Office of Policy and Planning |
| `170100225` | `NYC_GOID_000287` | Mayor's Office of Risk Management and Compliance | Office of Risk Management and Compliance |
| `170100246` | `NYC_GOID_000277` | Mayor's Office of Special Enforcement | Office of Special Enforcement |
| `170011032` | `NYC_GOID_000278` | Mayor's Office of Special Projects and Community Events | Office of Special Projects and Community Events |
| `170100241` | `NYC_GOID_000279` | Mayor's Office of Sports, Wellness and Recreation | Office of Sports, Wellness and Recreation |
| `170100029` | `NYC_GOID_000280` | Mayor's Office of Strategic Partnerships | Office of Strategic Partnerships |
| `170011049` | `NYC_GOID_000281` | Mayor's Office of Talent and Workforce Development | Office of Workforce Development |
| `170100228` | `NYC_GOID_000283` | Mayor's Office of Youth Employment | Office of Youth Employment |
| `170011009` | `NYC_GOID_000253` | Mayor's Office to End Domestic and Gender-Based Violence | Office to End Domestic Violence and Gender-Based Violence |
| `170100245` | `NYC_GOID_100018` | Mayor's Office to Prevent Gun Violence | Office to Prevent Gun Violence |
| `170100020` | `NYC_GOID_000286` | Mayor's Office to Protect Tenants | Office to Protect Tenants |
| `170100009` | `NYC_GOID_000293` | Mayor's Public Engagement Unit | Public Engagement Unit |
| `170010819` | `NYC_GOID_000318` | NYC Health + Hospitals | Health and Hospitals Corporation |
| `170100005` | `NYC_GOID_000000` | NYC311 | NYC 311 |
| `170100014` | `NYC_GOID_000312` | New York City Children's Cabinet | Children's Cabinet |
| `170010102` | `NYC_GOID_000097` | New York City Council | City Council |
| `170010827` | `NYC_GOID_000152` | New York City Department of Sanitation | Department of Sanitation |
| `170010841` | `NYC_GOID_000157` | New York City Department of Transportation | Department of Transportation |
| `170010017` | `NYC_GOID_000315` | New York City Emergency Management | Department of Emergency Management |
| `170019003` | `NYC_GOID_000316` | New York City Employee Retirement System | Employees Retirement System |
| `170020034` | `NYC_GOID_000319` | New York City Housing Authority | NYC Housing Authority |
| `170010025` | `NYC_GOID_000238` | New York City Law Department | Law Department |
| `170019017` | `NYC_GOID_000308` | New York City Municipal Water Finance Authority | NYC Municipal Water Finance Authority |
| `170010008` | `NYC_GOID_000343` | New York City Office of the Actuary | Office of the Actuary |
| `170010056` | `NYC_GOID_000389` | New York City Police Department | Police Department |
| `170019008` | `NYC_GOID_000390` | New York City Police Pension Fund | Police Pension Fund |
| `170010040` | `NYC_GOID_000143` | New York City Public Schools | Department of Education |
| `170010156` | `NYC_GOID_000436` | New York City Taxi and Limousine Commission | Taxi & Limousine Commission |
| `170019006` | `NYC_GOID_000310` | New York City Tourism + Conventions | NYC & Company |
| `170011024` | `NYC_GOID_000468` | New York City Young Men's Initiative | Young Men’s Initiative |
| `170019009` | `NYC_GOID_000334` | New York County Public Administrator | Public Administrator |
| `170100022` | `NYC_GOID_000380` | Office of Scheduling and Executive Operations | Scheduling and Executive Operations |
| `170019001` | `NYC_GOID_000344` | Office of the Administrative Justice Coordinator | Office of Administrative Justice Coordinator |
| `170010012` | `NYC_GOID_000027` | Office of the Borough President of Brooklyn | Brooklyn Borough President |
| `170010010` | `NYC_GOID_000028` | Office of the Borough President of Manhattan | Manhattan Borough President |
| `170010013` | `NYC_GOID_000029` | Office of the Borough President of Queens | Queens Borough President |
| `170010014` | `NYC_GOID_000030` | Office of the Borough President of Staten Island | Staten Island Borough President |
| `170010011` | `NYC_GOID_000026` | Office of the Borough President of The Bronx | Bronx Borough President |
| `170011026` | `NYC_GOID_100021` | Office of the Chief Medical Examiner | Office of Chief Medical Examiner |
| `170010103` | `NYC_GOID_100009` | Office of the City Clerk | City Clerk |
| `170010002` | `NYC_GOID_000251` | Office of the Mayor | Mayor's Office |
| `170010015` | `NYC_GOID_000123` | Office of the New York City Comptroller | Office of the Comptroller |
| `170010101` | `NYC_GOID_000396` | Office of the Public Advocate | Public Advocate |
| `170010906` | `NYC_GOID_100002` | Office of the Special Narcotics Prosecutor | Office of Prosecutor & Special Narcotics |
| `170010944` | `NYC_GOID_000401` | Public Administrator of Queens County | Public Administrator - Queens |
| `170010904` | `NYC_GOID_000171` | Queens District Attorney's Office | District Attorney - Queens |
| `170010945` | `NYC_GOID_000412` | Richmond County Public Administrator | Public Administrator - Richmond |
| `170011015` | `NYC_GOID_000425` | Special Commissioner of Investigation for the New York City School District | Special Commissioner of Investigation for the NYC School District |
| `170010905` | `NYC_GOID_000172` | Staten Island District Attorney's Office | District Attorney - Richmond |
| `170019014` | `NYC_GOID_000437` | Teachers' Retirement System of City of New York | Teachers' Retirement System |
| `170019037` | `NYC_GOID_000445` | Tobacco Settlement Asset Securitization Corporation | TSASC, Inc |

