# Real APE retrofit recommendation examples

Deterministic selection: seed `20261019`; 20 certificates and 41 intervention rows. Source files: `/home/mdeluca/murena/backend/data/metadata/extracted/ape_raw.parquet` and `/home/mdeluca/murena/backend/data/metadata/extracted/ape_recommendations.parquet`.

Values labeled **Observed** are copied from Phase 1 Parquet. **Calculated** values use the certificate's overall reachable EPgl,nren and are not intervention-level savings. Individual recommendation outcomes are shown separately; recommendations are never summed.

## Comparison summary

| Certificate | Municipality | Use code | Initial class | Initial EPgl,nren | Overall reachable class / EPgl,nren | Calculated reduction | Interventions |
|---|---|---|---|---:|---|---:|---:|
| ea05b5ee149a270b2f998a508c98b48f5147c826dfd707e86932250310487cd0 | Savigliano | 0 | C | 104.76 | A4 / 32.85 | 71.91 (68.6%) | 1 |
| 10414dcc489e84b86b972265e96d69dc23f639eae8a346dcbbd6a6de3a85edb1 | Casteldelfino | 9 | B | 225.18 | A1 / 189.87 | 35.31 (15.7%) | 2 |
| cc2ceabdf5c0fe21770aa13e17d6e3c580c0eb0b410682c19f41088e75ff7bf7 | Dronero | 14 | G | 391.03 | G / 280.0 | 111.03 (28.4%) | 1 |
| 4442dcf3a8afe2d69f62031549e250bb3202a395f482a04a106f444cd99dc854 | AIRASCA | 8 | E | 598.95 | E / 547.6 | 51.35 (8.6%) | 2 |
| 4ce7a23651a2ff833959ab9ff2eb019c8e78c2fbbbb9bf7cf940507aeaa4bbc5 | Villanova Monferrato | 4 | A4 | 0.0 | A4 / 0.0 | Missing | 1 |
| 8580ae016adbd9427febc54d618788daf9806e778de9afe57ebf92c75bfa6807 | BARDONECCHIA | 2 | F | 216.43 | E / 151.33 | 65.10 (30.1%) | 2 |
| 9bb256af9a9f13e28b6642b2b74cc278c360c5bf1d501f0379408f69b26832e8 | Stresa | 3 | D | 45.14 | B / 1.0 | 44.14 (97.8%) | 2 |
| 603652e743295495d31bdb36cae7879326560072a02277c196e0585a318e16b4 | BORGOMANERO | 5 | A1 | 383.9 | A2 / 264.36 | 119.54 (31.1%) | 1 |
| 3c614f33c2123d3b8cfb9648062961cadb9c79e77ef96c4c5c46293fe0851306 | Vignole Borbera | 13 | A2 | 41.24 | A4 / 23.45 | 17.79 (43.1%) | 1 |
| 13eb997e1dd9d69268df968c346688bd125a6ae911b64eb7ff70cdd51886827a | Torino | 12 | A3 | 213.02 | A3 / 193.01 | 20.01 (9.4%) | 1 |
| 463e28cda8c604648e586e1906b688db33c9147a4d2110517e23ba456d5b0ae7 | NOVARA | 1 | F | 378.34 | A4 / 42.35 | 335.99 (88.8%) | 2 |
| 16e09cbe49fe31c40144ac43afb4191d20cdea746df0d446b8d9b3b6d3246abd | Verbania | 6 | D | 409.85 | D / 394.71 | 15.14 (3.7%) | 2 |
| 8665636a7d24cdbfe54112bfe09c3912409e3e88b1aae816ac04553ba05c0cf7 | ASTI | 11 | G | 136.3 | A4 / 1.59 | 134.71 (98.8%) | 4 |
| f0f67deff0c247508047dd511d7b39eec66b44b1864edd152259d9f5e6eaadd0 | Pessinetto | 7 | E | 446.6 | B / 207.99 | 238.61 (53.4%) | 3 |
| 6f4ea638de9feb55310ab0efe44529c9182b9406cb9c1f09e321ca2017c4781f | Orta San Giulio | 10 | A1 | 1825.39 | A1 / 1817.23 | 8.16 (0.4%) | 1 |
| 5c69b33acc0061598250b12e1cadd16ccfbfd670b3a3fdb2832a99cabebc13b0 | Asti | 0 | C | 189.65 | A1 / 128.72 | 60.93 (32.1%) | 2 |
| 00d79d724d8c73fa2734a885c9924c9c08689eb3e3f3549b77bb9da8ff0886a2 | Villanova Mondovì | 2 | B | 83.12 | A3 / 43.86 | 39.26 (47.2%) | 3 |
| 8cfc16b19a5f9dd859efca124f344b383dc216d56db99bd0dcf38f38f73b12f1 | TORTONA | 9 | A2 | 155.05 | A4 / 36.54 | 118.51 (76.4%) | 3 |
| 619ebf14af7e5f6e0092d3a886d7572f26b0320e3908589445120170f43d0731 | SAVIGLIANO | 4 | E | 103.32 | D / 73.26 | 30.06 (29.1%) | 2 |
| a8c5ddec4c277e6aef687603e293a59c1f36493ab9b40e2e05442f119732912a | CONDOVE | 0 | A4 | 9.97 | A4 / 9.97 | 0.00 (0.0%) | 5 |

## Certificate details

### 1. `ea05b5ee149a270b2f998a508c98b48f5147c826dfd707e86932250310487cd0`

- **Observed building data:** municipality Savigliano; building-use code 0; attestation object 1; construction year 1770.0; heated usable surface 118.54 m²; initial class C; initial EPgl,nren 104.76.
- **Observed overall APE reachable performance:** class A4; EPgl,nren 32.85.
- **Calculated overall potential reduction:** 71.91 kWh/m²·year (68.64%).
- **Observed recommended interventions:**
  - Code 0: Coibentazione strutture opache non isolate (major renovation: false; payback: 10.0 years; intervention reachable class: A4; intervention reachable EPgl,nren: 32.85).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 2. `10414dcc489e84b86b972265e96d69dc23f639eae8a346dcbbd6a6de3a85edb1`

- **Observed building data:** municipality Casteldelfino; building-use code 9; attestation object 1; construction year 1960.0; heated usable surface 44.0 m²; initial class B; initial EPgl,nren 225.18.
- **Observed overall APE reachable performance:** class A1; EPgl,nren 189.87.
- **Calculated overall potential reduction:** 35.31 kWh/m²·year (15.68%).
- **Observed recommended interventions:**
  - Code 0: Fabbricato - involucro opaco (major renovation: false; payback: 12.2 years; intervention reachable class: A1; intervention reachable EPgl,nren: 195.32).
  - Code 1: Sostituzione serramenti esterni (major renovation: false; payback: 78.2 years; intervention reachable class: A1; intervention reachable EPgl,nren: 219.74).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 3. `cc2ceabdf5c0fe21770aa13e17d6e3c580c0eb0b410682c19f41088e75ff7bf7`

- **Observed building data:** municipality Dronero; building-use code 14; attestation object 0; construction year 1987.0; heated usable surface 194.2 m²; initial class G; initial EPgl,nren 391.03.
- **Observed overall APE reachable performance:** class G; EPgl,nren 280.0.
- **Calculated overall potential reduction:** 111.03 kWh/m²·year (28.39%).
- **Observed recommended interventions:**
  - Code 3: Sostituzione generatore di calore (major renovation: false; payback: 10.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 280.0).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 4. `4442dcf3a8afe2d69f62031549e250bb3202a395f482a04a106f444cd99dc854`

- **Observed building data:** municipality AIRASCA; building-use code 8; attestation object 1; construction year 1970.0; heated usable surface 82.84 m²; initial class E; initial EPgl,nren 598.95.
- **Observed overall APE reachable performance:** class E; EPgl,nren 547.6.
- **Calculated overall potential reduction:** 51.35 kWh/m²·year (8.57%).
- **Observed recommended interventions:**
  - Code 0: Isolamento strutture opache verticali verso l'esterno (major renovation: 0; payback: 16.0 years; intervention reachable class: E; intervention reachable EPgl,nren: 587.44).
  - Code 4: Sostituzione generatore combinato (major renovation: 1; payback: 5.0 years; intervention reachable class: E; intervention reachable EPgl,nren: 558.28).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 5. `4ce7a23651a2ff833959ab9ff2eb019c8e78c2fbbbb9bf7cf940507aeaa4bbc5`

- **Observed building data:** municipality Villanova Monferrato; building-use code 4; attestation object 0; construction year 2018.0; heated usable surface 927.88 m²; initial class A4; initial EPgl,nren 0.0.
- **Observed overall APE reachable performance:** class A4; EPgl,nren 0.0.
- **Calculated overall potential reduction:** Missing; baseline and/or reachable EPgl,nren is absent or not positive numeric data.
- **Observed recommended interventions:**
  - Code 5: Solare termico (major renovation: false; payback: 30.0 years; intervention reachable class: A4; intervention reachable EPgl,nren: 0.0).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 6. `8580ae016adbd9427febc54d618788daf9806e778de9afe57ebf92c75bfa6807`

- **Observed building data:** municipality BARDONECCHIA; building-use code 2; attestation object 1; construction year 1993.0; heated usable surface 30.95 m²; initial class F; initial EPgl,nren 216.43.
- **Observed overall APE reachable performance:** class E; EPgl,nren 151.33.
- **Calculated overall potential reduction:** 65.10 kWh/m²·year (30.08%).
- **Observed recommended interventions:**
  - Code 0: Isolamento strutture opache verticali verso l'esterno (major renovation: 0; payback: 15.0 years; intervention reachable class: F; intervention reachable EPgl,nren: 201.56).
  - Code 5: Installazione impianto solare termico per ACS (major renovation: 0; payback: 5.0 years; intervention reachable class: E; intervention reachable EPgl,nren: 163.67).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 7. `9bb256af9a9f13e28b6642b2b74cc278c360c5bf1d501f0379408f69b26832e8`

- **Observed building data:** municipality Stresa; building-use code 3; attestation object 1; construction year 1900.0; heated usable surface 1055.42 m²; initial class D; initial EPgl,nren 45.14.
- **Observed overall APE reachable performance:** class B; EPgl,nren 1.0.
- **Calculated overall potential reduction:** 44.14 kWh/m²·year (97.78%).
- **Observed recommended interventions:**
  - Code 2: Installazione/sostituzione ventilazione meccanica (major renovation: 0; payback: 5.0 years; intervention reachable class: A4; intervention reachable EPgl,nren: 0.3).
  - Code 5: Installazione impianto solare fotovoltaico (major renovation: 0; payback: 5.0 years; intervention reachable class: B; intervention reachable EPgl,nren: 1.0).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 8. `603652e743295495d31bdb36cae7879326560072a02277c196e0585a318e16b4`

- **Observed building data:** municipality BORGOMANERO; building-use code 5; attestation object 1; construction year 2005.0; heated usable surface 132.53 m²; initial class A1; initial EPgl,nren 383.9.
- **Observed overall APE reachable performance:** class A2; EPgl,nren 264.36.
- **Calculated overall potential reduction:** 119.54 kWh/m²·year (31.14%).
- **Observed recommended interventions:**
  - Code 1: sostituzione serramenti esistenti lato EST (major renovation: false; payback: 9.0 years; intervention reachable class: A2; intervention reachable EPgl,nren: 264.36).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 9. `3c614f33c2123d3b8cfb9648062961cadb9c79e77ef96c4c5c46293fe0851306`

- **Observed building data:** municipality Vignole Borbera; building-use code 13; attestation object 0; construction year 2021.0; heated usable surface 1106.82 m²; initial class A2; initial EPgl,nren 41.24.
- **Observed overall APE reachable performance:** class A4; EPgl,nren 23.45.
- **Calculated overall potential reduction:** 17.79 kWh/m²·year (43.14%).
- **Observed recommended interventions:**
  - Code 2: Sostituzione scaldacqua elettrici con scaldacqua in pompa di calore (major renovation: false; payback: 1.3 years; intervention reachable class: A4; intervention reachable EPgl,nren: 23.45).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 10. `13eb997e1dd9d69268df968c346688bd125a6ae911b64eb7ff70cdd51886827a`

- **Observed building data:** municipality Torino; building-use code 12; attestation object 0; construction year 2017.0; heated usable surface 4169.32 m²; initial class A3; initial EPgl,nren 213.02.
- **Observed overall APE reachable performance:** class A3; EPgl,nren 193.01.
- **Calculated overall potential reduction:** 20.01 kWh/m²·year (9.39%).
- **Observed recommended interventions:**
  - Code 4: Impianto solare termico per produzione ACS (major renovation: false; payback: 25.0 years; intervention reachable class: A3; intervention reachable EPgl,nren: 193.01).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 11. `463e28cda8c604648e586e1906b688db33c9147a4d2110517e23ba456d5b0ae7`

- **Observed building data:** municipality NOVARA; building-use code 1; attestation object 1; construction year 1800.0; heated usable surface 1534.77 m²; initial class F; initial EPgl,nren 378.34.
- **Observed overall APE reachable performance:** class A4; EPgl,nren 42.35.
- **Calculated overall potential reduction:** 335.99 kWh/m²·year (88.81%).
- **Observed recommended interventions:**
  - Code 1: Sostituzione serramenti esterni - vetro B.E. (major renovation: false; payback: 7.0 years; intervention reachable class: F; intervention reachable EPgl,nren: 324.22).
  - Code 2: Sostituzione generatore climatizzazione invernale - caldaia condensazione (major renovation: false; payback: 2.0 years; intervention reachable class: A3; intervention reachable EPgl,nren: 47.99).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 12. `16e09cbe49fe31c40144ac43afb4191d20cdea746df0d446b8d9b3b6d3246abd`

- **Observed building data:** municipality Verbania; building-use code 6; attestation object 0; construction year 1916.0; heated usable surface 1570.55 m²; initial class D; initial EPgl,nren 409.85.
- **Observed overall APE reachable performance:** class D; EPgl,nren 394.71.
- **Calculated overall potential reduction:** 15.14 kWh/m²·year (3.69%).
- **Observed recommended interventions:**
  - Code 0: 2-isolamento solaio verso sottotetto (major renovation: false; payback: 33.21 years; intervention reachable class: D; intervention reachable EPgl,nren: 407.49).
  - Code 2: 1-installazione di sistema di egolazione per singolo ambiente (major renovation: false; payback: 0.67 years; intervention reachable class: D; intervention reachable EPgl,nren: 397.03).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 13. `8665636a7d24cdbfe54112bfe09c3912409e3e88b1aae816ac04553ba05c0cf7`

- **Observed building data:** municipality ASTI; building-use code 11; attestation object 0; construction year 1950.0; heated usable surface 1309.3 m²; initial class G; initial EPgl,nren 136.3.
- **Observed overall APE reachable performance:** class A4; EPgl,nren 1.59.
- **Calculated overall potential reduction:** 134.71 kWh/m²·year (98.83%).
- **Observed recommended interventions:**
  - Code 0: Isolamento coperture esterne (major renovation: 0; payback: 2.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 135.37).
  - Code 0: Isolamento strutture opache verticali verso l'esterno (major renovation: 0; payback: 1.0 years; intervention reachable class: F; intervention reachable EPgl,nren: 125.93).
  - Code 1: Sostituzione componenti finestrati (major renovation: 0; payback: 11.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 134.37).
  - Code 4: Sostituzione generatore combinato (major renovation: 0; payback: 1.0 years; intervention reachable class: A4; intervention reachable EPgl,nren: 1.54).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 14. `f0f67deff0c247508047dd511d7b39eec66b44b1864edd152259d9f5e6eaadd0`

- **Observed building data:** municipality Pessinetto; building-use code 7; attestation object 0; construction year 1900.0; heated usable surface 121.26 m²; initial class E; initial EPgl,nren 446.6.
- **Observed overall APE reachable performance:** class B; EPgl,nren 207.99.
- **Calculated overall potential reduction:** 238.61 kWh/m²·year (53.43%).
- **Observed recommended interventions:**
  - Code 0: 1-INSTALLAZIONE DI ISOLANTE A CAPPOTTO SUL LATO INTERNO DELLE MURATURE VERSO L'ESTERNO (major renovation: false; payback: 2.0 years; intervention reachable class: D; intervention reachable EPgl,nren: 284.42).
  - Code 2: 2-INSTALLAZIONE DI POMPA DI CALORE ELETTRICA PER PRODUZIONE COMBINATA DI RISCALDAMENTO E ACS (major renovation: false; payback: 2.5 years; intervention reachable class: E; intervention reachable EPgl,nren: 375.01).
  - Code 5: 3-INSTALLAZIONE DI PANNELLI SOLARI FOTOVOLTAICI (major renovation: false; payback: 24.0 years; intervention reachable class: E; intervention reachable EPgl,nren: 419.64).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 15. `6f4ea638de9feb55310ab0efe44529c9182b9406cb9c1f09e321ca2017c4781f`

- **Observed building data:** municipality Orta San Giulio; building-use code 10; attestation object 1; construction year 1930.0; heated usable surface 112.49 m²; initial class A1; initial EPgl,nren 1825.39.
- **Observed overall APE reachable performance:** class A1; EPgl,nren 1817.23.
- **Calculated overall potential reduction:** 8.16 kWh/m²·year (0.45%).
- **Observed recommended interventions:**
  - Code 0: Cappotto interno parete opaca disperdente (major renovation: false; payback: 8.5 years; intervention reachable class: A1; intervention reachable EPgl,nren: 1817.23).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 16. `5c69b33acc0061598250b12e1cadd16ccfbfd670b3a3fdb2832a99cabebc13b0`

- **Observed building data:** municipality Asti; building-use code 0; attestation object 1; construction year 1940.0; heated usable surface 42.5 m²; initial class C; initial EPgl,nren 189.65.
- **Observed overall APE reachable performance:** class A1; EPgl,nren 128.72.
- **Calculated overall potential reduction:** 60.93 kWh/m²·year (32.13%).
- **Observed recommended interventions:**
  - Code 1: sostituzione serramenti (major renovation: false; payback: 4.0 years; intervention reachable class: B; intervention reachable EPgl,nren: 157.95).
  - Code 4: sostituzione boiler (major renovation: false; payback: 1.0 years; intervention reachable class: B; intervention reachable EPgl,nren: 160.42).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 17. `00d79d724d8c73fa2734a885c9924c9c08689eb3e3f3549b77bb9da8ff0886a2`

- **Observed building data:** municipality Villanova Mondovì; building-use code 2; attestation object 0; construction year 1850.0; heated usable surface 50.3 m²; initial class B; initial EPgl,nren 83.12.
- **Observed overall APE reachable performance:** class A3; EPgl,nren 43.86.
- **Calculated overall potential reduction:** 39.26 kWh/m²·year (47.23%).
- **Observed recommended interventions:**
  - Code 0: COIBENTAZIONE DI TIPO A CAPPOTTO PARETI PERIMETRALI (major renovation: true; payback: 15.0 years; intervention reachable class: A1; intervention reachable EPgl,nren: 68.86).
  - Code 1: SOSTITUZIONE SERRAMENTI (major renovation: false; payback: 10.0 years; intervention reachable class: A1; intervention reachable EPgl,nren: 70.9).
  - Code 2: ISTALLAZIONE CALDAIA (major renovation: false; payback: 15.0 years; intervention reachable class: A1; intervention reachable EPgl,nren: 70.9).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 18. `8cfc16b19a5f9dd859efca124f344b383dc216d56db99bd0dcf38f38f73b12f1`

- **Observed building data:** municipality TORTONA; building-use code 9; attestation object 1; construction year 1920.0; heated usable surface 32.67 m²; initial class A2; initial EPgl,nren 155.05.
- **Observed overall APE reachable performance:** class A4; EPgl,nren 36.54.
- **Calculated overall potential reduction:** 118.51 kWh/m²·year (76.43%).
- **Observed recommended interventions:**
  - Code 0: Pareti verso esterno (Interno) (major renovation: false; payback: 26.0 years; intervention reachable class: A2; intervention reachable EPgl,nren: 149.14).
  - Code 1: Sostituzione infissi (Uw: 1,400) e applicazione di schermature (Tipo: Veneziane bianche - INTERNA) (major renovation: false; payback: 26.0 years; intervention reachable class: A2; intervention reachable EPgl,nren: 118.12).
  - Code 5: Installazione dei seguenti impianti: Fotovoltaico (major renovation: false; payback: 26.0 years; intervention reachable class: A4; intervention reachable EPgl,nren: 54.02).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 19. `619ebf14af7e5f6e0092d3a886d7572f26b0320e3908589445120170f43d0731`

- **Observed building data:** municipality SAVIGLIANO; building-use code 4; attestation object 1; construction year 1500.0; heated usable surface 93.76 m²; initial class E; initial EPgl,nren 103.32.
- **Observed overall APE reachable performance:** class D; EPgl,nren 73.26.
- **Calculated overall potential reduction:** 30.06 kWh/m²·year (29.09%).
- **Observed recommended interventions:**
  - Code 2: Sotituzione generatore con caldaia a condensazione (major renovation: false; payback: 20.0 years; intervention reachable class: D; intervention reachable EPgl,nren: 75.74).
  - Code 4: Installazione boiler a pompa di calore (major renovation: false; payback: 86.0 years; intervention reachable class: E; intervention reachable EPgl,nren: 100.84).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

### 20. `a8c5ddec4c277e6aef687603e293a59c1f36493ab9b40e2e05442f119732912a`

- **Observed building data:** municipality CONDOVE; building-use code 0; attestation object 0; construction year 1000.0; heated usable surface 247.41 m²; initial class A4; initial EPgl,nren 9.97.
- **Observed overall APE reachable performance:** class A4; EPgl,nren 9.97.
- **Calculated overall potential reduction:** 0.00 kWh/m²·year (0.00%).
- **Observed recommended interventions:**
  - Code 0: Intervento su componenti opachi (major renovation: false; payback: 1.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 0.0).
  - Code 1: Intervento su infissi (major renovation: false; payback: 1.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 0.0).
  - Code 2: Intervento su impianti di climatizzazione invernale (major renovation: false; payback: 1.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 0.0).
  - Code 3: Intervento su impianti di climatizzazione estiva (major renovation: false; payback: 1.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 0.0).
  - Code 5: Intervento su fonti rinnovabili (major renovation: false; payback: 1.0 years; intervention reachable class: G; intervention reachable EPgl,nren: 0.0).
- **Missing or ambiguous:** Missing fields are labeled above. Source codes are retained verbatim; use and attestation codes are not reinterpreted. Recommendation outcomes are individual estimates and do not represent additive savings.

## Intervention type distribution

| Observed intervention code | Rows |
|---|---:|
| 0 | 12 |
| 1 | 8 |
| 2 | 8 |
| 3 | 2 |
| 4 | 5 |
| 5 | 6 |

## Provenance and calculation

The CSV has one row per documented recommendation, joined by `source_record_id`. Building fields and recommendation fields are observed Parquet values. The two calculated reduction columns use the certificate-level baseline `epglnren` and certificate-level overall reachable `overall_reachable_epglnren`; recommendation-level reachable values remain separate. No personal contacts, addresses, or cadastral identifiers are exported. Selection is a seeded greedy coverage procedure across classes, use codes, construction decades, surface bands, intervention-code combinations, improvement bands, valid energy metrics, and multiple-intervention certificates.
