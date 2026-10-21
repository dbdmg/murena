from __future__ import annotations
import hashlib, json, random
from pathlib import Path
import numpy as np
import pandas as pd
from .core import VERSION, FIELDS, DEFAULT_SCORING_CONFIG, validate_scenario

USE_CASES = ["community_healthcare", "social_community_center", "libraries_cultural_facilities",
 "educational_training_spaces", "public_administration_offices", "social_housing", "climate_shelters", "multifunctional_community_hubs"]
NUMERIC = ["heated_usable_surface", "construction_year", "epglnren", "co2_emissions", "heating_energy_need"]
PREFERENCE_PAIRS = [("heated_usable_surface", "maximize"), ("epglnren", "minimize"),
                    ("co2_emissions", "minimize"), ("heating_energy_need", "minimize")]
USECASE_FIELDS = {
 "community_healthcare": {"heated_usable_surface","dpr412_class_code","construction_year","energy_class","epglnren"},
 "social_community_center": {"heated_usable_surface","dpr412_class_code","construction_year","energy_class"},
 "libraries_cultural_facilities": {"heated_usable_surface","dpr412_class_code","construction_year","energy_class"},
 "educational_training_spaces": {"heated_usable_surface","dpr412_class_code","construction_year","energy_class"},
 "public_administration_offices": {"heated_usable_surface","dpr412_class_code","construction_year","energy_class"},
 "social_housing": {"heated_usable_surface","construction_year","energy_class","epglnren"},
 "climate_shelters": {"heated_usable_surface","energy_class","heating_service_present","cooling_service_present"},
 "multifunctional_community_hubs": {"heated_usable_surface","dpr412_class_code","construction_year","energy_class","epglnren"}}

def generate_scenarios(candidate_path: Path, output_path: Path, count: int = 200, seed: int = 20261019) -> dict:
    if count % 2: raise ValueError("pilot count must be even to balance sampling strategies")
    df = pd.read_parquet(candidate_path, columns=["heated_usable_surface", "construction_year", "energy_class", "epglnren", "co2_emissions", "heating_energy_need", "cooling_energy_need", "dpr412_class_code", "istat_code"])
    rng = random.Random(seed); np_rng = np.random.default_rng(seed)
    quantiles = {f: np.nanquantile(pd.to_numeric(df[f], errors="coerce"), [.1,.25,.5,.75,.9]).tolist() for f in NUMERIC}
    available_preferences={f for f in {x[0] for x in PREFERENCE_PAIRS}|{"cooling_energy_need"} if f in df.columns and df[f].notna().any()}
    classes = sorted(x for x in df.energy_class.dropna().astype(str).unique() if x in {"A1","A2","A3","A4","B","C","D","E","F","G"})
    uses = sorted(x for x in df.dpr412_class_code.dropna().astype(str).unique())
    istats = sorted(x for x in df.istat_code.dropna().astype(str).unique() if x)
    used=set(); records=[]; rejection={"duplicate_semantics": 0}
    for idx in range(count):
        strategy = "A_distribution_independent" if idx < count//2 else "B_dataset_aware"
        local = idx if idx < count//2 else idx-count//2
        uc = USE_CASES[local % len(USE_CASES)]
        n_constraints = 1 + (local % 3)
        constraints=[]; attrs=[]
        options = [x for x in ["heated_usable_surface", "energy_class", "construction_year", "epglnren", "dpr412_class_code"] if x in USECASE_FIELDS[uc]]
        rng.shuffle(options)
        for opt in options:
            if len(attrs) >= n_constraints: break
            if opt in attrs: continue
            attrs.append(opt)
            cid=f"c{len(attrs)}"
            if strategy.startswith("A_"):
                if opt == "heated_usable_surface": op="gte"; val=rng.choice([30,60,100,200,500])
                elif opt == "energy_class": op="in"; val=rng.choice([["A1","A2","A3","A4"],["A1","A2","A3","A4","B"],["E","F","G"]])
                elif opt == "construction_year": op="between"; val=rng.choice([[1800,1945],[1946,1980],[1981,2025]])
                elif opt == "epglnren": op="lte"; val=rng.choice([50,100,200,400])
                else:
                    if not uses: continue
                    op="eq"; val=rng.choice(uses)
            else:
                if opt == "heated_usable_surface": op="gte"; val=float(rng.choice(quantiles[opt]))
                elif opt == "energy_class":
                    if not classes: continue
                    op="eq"; val=rng.choice(classes)
                elif opt == "construction_year": op="gte" if rng.random()<.5 else "lte"; val=float(rng.choice(quantiles[opt]))
                elif opt == "epglnren": op="lte" if rng.random()<.6 else "gte"; val=float(rng.choice(quantiles[opt]))
                else:
                    if not uses: continue
                    op="eq"; val=rng.choice(uses)
            constraints.append({"constraint_id":cid,"attribute":opt,"operator":op,"value":val,
                "unit":"m2" if opt=="heated_usable_surface" else ("year" if opt=="construction_year" else None),
                "source":"fixed_experimental_distribution" if strategy.startswith("A_") else "candidate_universe_quantile",
                "missing_behavior":"unknown"})
        usable_preferences=PREFERENCE_PAIRS if uc!="climate_shelters" else PREFERENCE_PAIRS + [("cooling_energy_need","minimize")]
        if uc!="climate_shelters": usable_preferences=[x for x in usable_preferences if x[0]!="heating_energy_need"]
        usable_preferences=[x for x in usable_preferences if x[0] in available_preferences]
        prefs = rng.sample(usable_preferences, 2)
        weights=[0.5,0.5] if local%2 else [0.65,0.35]
        pref=[{"attribute":a,"direction":d,"weight":w,"normalization":"fixed_bounds_clipped_minmax_v1"} for (a,d),w in zip(prefs,weights)]
        # Small geography scopes are sampled independently of the outcome; the scope is also
        # represented as an explicit hard constraint so the oracle semantics are unambiguous.
        scope = {"type":"all","value":None}
        if local % 5 == 4 and istats:
            code=rng.choice(istats); scope={"type":"istat_code","value":code}
            constraints.append({"constraint_id":"geographic_scope","attribute":"istat_code","operator":"eq","value":code,
                "unit":None,"source":"candidate_universe_geographic_scope_sampling","missing_behavior":"unknown"})
        scenario={"scenario_id":f"CB-{('A' if strategy.startswith('A_') else 'B')}-{local+1:04d}",
          "use_case_id":uc,"candidate_universe_version":VERSION,"scoring_config_version":DEFAULT_SCORING_CONFIG["version"],"geographic_scope":scope,
          "hard_constraints":constraints,"preferences":pref,"missing_value_policy":"include_unknown_separately",
          "normalization_method":"fixed_bounds_clipped_minmax_v1",
          "expected_behavior":{"unknown_candidates":"reported separately from confirmed eligible and ineligible","ranked_population":"confirmed eligible only","incomplete_preference_evidence":"unranked"},
          "generation_metadata":{"strategy":strategy,"seed":seed,"difficulty":"pending_oracle_measurement","requested_hard_constraint_count":len(constraints),"requested_preference_count":len(pref),"sampling_attempt":1}}
        attempt=0
        while True:
            validate_scenario(scenario)
            canonical=json.dumps({k:v for k,v in scenario.items() if k not in {"scenario_id","generation_metadata"}},sort_keys=True,separators=(",",":"))
            key=hashlib.sha256(canonical.encode()).hexdigest()
            if key not in used: break
            rejection["duplicate_semantics"]+=1; attempt+=1
            if attempt>100: raise RuntimeError("could not generate unique scenario after 100 deterministic weight samples")
            # Keep sampled constraints fixed and resample declared preference weights;
            # this changes the decision scenario without selecting any target candidate.
            w=0.25+0.005*attempt
            scenario["preferences"][0]["weight"]=round(w,3)
            scenario["preferences"][1]["weight"]=round(1-w,3)
        scenario["generation_metadata"]["sampling_attempt"]=attempt+1
        used.add(key); records.append(scenario)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text("".join(json.dumps(s,ensure_ascii=False,sort_keys=True)+"\n" for s in records),encoding="utf-8")
    report={"count":len(records),"seed":seed,"strategy_counts":{"A_distribution_independent":count//2,"B_dataset_aware":count//2},
      "use_case_counts":{u:sum(s["use_case_id"]==u for s in records) for u in USE_CASES},"rejection_reasons":rejection,
      "threshold_quantiles":quantiles,"category_vocabularies":{"energy_class":classes,"dpr412_class_code":uses},
      "unavailable_preference_attributes_excluded":sorted(({x[0] for x in PREFERENCE_PAIRS}|{"cooling_energy_need"})-available_preferences),
      "note":"A has fixed explicit experimental thresholds and random draws; B uses empirical candidate quantiles. Preference attributes with no observed values in the candidate snapshot are not sampled. No target candidate is selected."}
    output_path.with_name("scenario_generation_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
