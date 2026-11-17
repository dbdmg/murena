"""Unit tests for the experiment harness (no LLM calls, no dataset).

Run from backend/:  uv run python -m unittest tests.test_experiments_metrics -v
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"
if str(EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS))

import benchmark_cli as bc  # noqa: E402
import compare_conditions as cc  # noqa: E402

V3 = EXPERIMENTS / "data" / "scenarios_v3"
V3_YAML = V3 / "conversational_scenarios.yaml"
V2_YAML = EXPERIMENTS / "data" / "scenarios_v2" / "conversational_scenarios.yaml"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_missingness_v3", V3 / "generate_missingness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RankingMetricTests(unittest.TestCase):
    def test_jaccard(self):
        self.assertEqual(cc.jaccard([1, 2, 3], [1, 2, 3]), 1.0)
        self.assertEqual(cc.jaccard([1, 2], [3, 4]), 0.0)
        self.assertAlmostEqual(cc.jaccard([1, 2, 3], [2, 3, 4]), 0.5)
        self.assertIsNone(cc.jaccard([], []))
        self.assertEqual(cc.jaccard([1], []), 0.0)

    def test_rbo_identical_and_disjoint(self):
        self.assertAlmostEqual(cc.rbo_ext(list("abcdefghij"), list("abcdefghij")), 1.0)
        self.assertAlmostEqual(cc.rbo_ext(list("abc"), list("xyz")), 0.0)
        self.assertIsNone(cc.rbo_ext([], []))
        self.assertEqual(cc.rbo_ext(["a"], []), 0.0)

    def test_rbo_known_value_equal_lengths(self):
        # X = (1, 1, 3): 0.25 * (0.8 + 0.5*0.64 + 1*0.512) + 1*0.512 = 0.92
        self.assertAlmostEqual(cc.rbo_ext([1, 2, 3], [1, 3, 2], p=0.8), 0.92)

    def test_rbo_unequal_lengths(self):
        # Prefix of the longer list extrapolates to full agreement.
        self.assertAlmostEqual(cc.rbo_ext(["a"], ["a", "b"]), 1.0)
        # S=[x], L=[y,x]: X1=0, X2=1 -> 0.25*0.32 + (1/2)*0.64 = 0.40
        self.assertAlmostEqual(cc.rbo_ext(["x"], ["y", "x"]), 0.40)
        self.assertAlmostEqual(cc.rbo_ext(["y", "x"], ["x"]), 0.40)
        value = cc.rbo_ext([1, 2, 3], [3, 4, 5, 1, 2])
        self.assertTrue(0.0 < value < 1.0)
        self.assertAlmostEqual(value, cc.rbo_ext([3, 4, 5, 1, 2], [1, 2, 3]))


class TieTests(unittest.TestCase):
    def test_tie_groups(self):
        self.assertEqual(cc.tie_groups([3, 3, 2, 1, 1, 1]), [[0, 1], [2], [3, 4, 5]])
        self.assertEqual(cc.tie_groups([None, None, 1]), [[0], [1], [2]])
        self.assertEqual(cc.tie_groups([1.0000001, 1.0000002]), [[0, 1]])

    def test_permutations_stay_within_groups_and_are_seeded(self):
        ids = ["a", "b", "c", "d", "e"]
        scores = [9, 9, 5, 1, 1]
        perms = cc.tie_permutations(ids, scores, 200, "seed")
        self.assertEqual(perms, cc.tie_permutations(ids, scores, 200, "seed"))
        for order in perms:
            self.assertEqual(set(order[:2]), {"a", "b"})
            self.assertEqual(order[2], "c")
            self.assertEqual(set(order[3:]), {"d", "e"})
        self.assertGreater(len({tuple(p) for p in perms}), 1)
        self.assertEqual(cc.tie_permutations(ids, [5, 4, 3, 2, 1], 3, "s"), [ids] * 3)

    def test_tie_expected_jaccard(self):
        comparer = cc.RankingComparer(permutations=2000, seed=13, p=0.8)
        tied = {"run_id": "a", "top": [{"id": str(i), "score": 50.0} for i in range(1, 7)]}
        strict = {"run_id": "b", "top": [{"id": str(i), "score": 100.0 - i} for i in range(1, 6)]}
        result = comparer.pair(tied, strict)
        self.assertEqual(result["jaccard5_served"], 1.0)
        # Top-5 of 6 tied items: E[J] = 1/6 * 1 + 5/6 * 4/6 = 0.7222
        self.assertAlmostEqual(result["jaccard5_tie_expected"], 0.7222, delta=0.03)
        self.assertIsNone(comparer.pair({"run_id": "c", "top": []}, {"run_id": "d", "top": []}))


class FilterAtomTests(unittest.TestCase):
    ROW = {
        "matched_use_cases": ["Micro-nursery"],
        "requirements": [],
        "sql_agent_sql": "SELECT * FROM ESTATES WHERE surface_area >= 140 AND energy_class IN ('A1','B','C') "
                         "AND mobility >= 71 AND haversine_km(latitude, longitude, 45.0, 7.6) <= 3.0",
        "extractions": {
            "building": {"typologies": ["Uffici e assimilabili"], "requirements": [
                {"target_column": "surface_area", "operator": ">=", "value": 140.0},
                {"target_column": "capacity_places", "operator": ">=", "value": 18},
            ]},
            "energy": {"requirements": [
                {"target_column": "energy_class", "operator": "IN", "value": ["A1", "A2", "A3", "A4", "B", "C"]}]},
            "proximity": {"requirements": [{"target_column": "mobility", "operator": ">=", "value": 71}]},
            "location": {"places": [{"name": "Turin", "city": "Torino", "radius_km": 3}]},
            "ranking": {"weights": {}},
        },
    }

    def test_filter_atoms(self):
        self.assertEqual(cc.filter_atoms(self.ROW), {
            "D:use=micro-nursery", "L:city=turin", "L:radius=3.0", "Cb:surface_area>=140",
            "Cb:capacity>=18", "Ce:worst=C", "Cp:mobility", "I:typology=uffici e assimilabili",
        })
        self.assertEqual(cc.filter_atoms({}), set())

    def test_energy_order_and_sql_consistency(self):
        self.assertEqual(cc.worst_energy_class(["A4", "B", "D", "C"]), "D")
        self.assertEqual(cc.worst_energy_class(["A1", "A4"]), "A1")
        atoms = cc.filter_atoms(self.ROW)
        consistent, checked = cc.sql_consistency(self.ROW, atoms)
        self.assertEqual((consistent, checked), (4, 4))

    def test_prf_and_majority(self):
        self.assertEqual(cc.atom_prf(set(), set())["f1"], 1.0)
        self.assertEqual(cc.atom_prf({"a"}, set())["f1"], 0.0)
        self.assertAlmostEqual(cc.atom_prf({"a", "b"}, {"a", "c"})["f1"], 0.5)
        sets = [{"a", "b"}, {"a"}, {"a", "c"}, {"b"}, {"a"}]
        self.assertEqual(cc.majority_atoms(sets), {"a"})              # >= 3 of 5
        self.assertEqual(cc.majority_atoms(sets[:3]), {"a"})          # >= 2 of 3
        self.assertEqual(cc.majority_atoms(sets, min_votes=2), {"a", "b"})


class UncertaintyTests(unittest.TestCase):
    def test_bootstrap_deterministic(self):
        values = {f"b{i}": float(i) for i in range(8)}
        first = cc.cluster_bootstrap(values, b=2000, seed=7)
        self.assertEqual(first, cc.cluster_bootstrap(values, b=2000, seed=7))
        self.assertAlmostEqual(first["mean"], 3.5)
        self.assertLess(first["ci_low"], 3.5)
        self.assertGreater(first["ci_high"], 3.5)
        self.assertEqual(cc.cluster_bootstrap({"a": None}, b=10)["n"], 0)

    def test_sign_flip(self):
        self.assertAlmostEqual(cc.sign_flip_test([1.0] * 8)["p_value"], 2 / 256)
        self.assertEqual(cc.sign_flip_test([1.0, -1.0])["p_value"], 1.0)
        self.assertIsNone(cc.sign_flip_test([])["p_value"])


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.gen = _load_generator()
        self.answers = {
            "I": "I am looking for an existing residential dwelling.",
            "D": "I intend to convert it into a micro-nursery for 18 children.",
            "L": "The location is in Turin.",
            "Cb": "I need a property with at least 140 sqm of gross floor area.",
            "Ce": "I prefer a property in energy class C or better.",
            "Cp": "I prefer properties near public transport.",
        }

    def test_split_capacity(self):
        derived = self.gen.split_capacity("UC01_micro_nursery_missing_use", self.answers)
        self.assertEqual(derived["D"], "I intend to convert it into a micro-nursery.")
        self.assertEqual(
            derived["Cb"], "I need a property with at least 140 sqm of gross floor area and capacity for 18 people.")
        self.assertEqual({k: v for k, v in derived.items() if k not in ("D", "Cb")},
                         {k: v for k, v in self.answers.items() if k not in ("D", "Cb")})
        self.assertIn("for 18 children", self.answers["D"], "source answers must not be mutated")

    def test_split_capacity_mid_sentence_and_errors(self):
        answers = dict(self.answers, D="I intend to create a spring section (sezione primavera) for 14 children, "
                                       "integrated into an existing kindergarten.")
        derived = self.gen.split_capacity("UC03_spring_missing_use", dict(answers, Cb=self.answers["Cb"]))
        self.assertEqual(derived["D"], "I intend to create a spring section (sezione primavera), "
                                       "integrated into an existing kindergarten.")
        with self.assertRaises(ValueError):
            self.gen.split_capacity("UC03_spring_missing_use", self.answers)  # phrase absent
        twice = dict(self.answers, D="A micro-nursery for 18 children and for 18 children.")
        with self.assertRaises(ValueError):
            self.gen.split_capacity("UC01_micro_nursery_missing_use", twice)

    def test_generated_files_have_no_capacity_in_d(self):
        triplets = json.loads((V3 / "scenario_triplets.json").read_text(encoding="utf-8"))
        self.assertEqual(len(triplets), 48)
        for entry in triplets:
            d = entry["conversational"]["simulated_user_answers_by_dimension"]["D"]
            self.assertIsNone(self.gen.CAPACITY_REGEX.search(d), entry["case_id"])


class RunnerTests(unittest.TestCase):
    def _args(self, *extra):
        return bc.build_parser().parse_args(["--scenarios", str(V3_YAML), *extra])

    def test_v3_job_construction(self):
        scenarios = bc.load_scenarios(V3_YAML)
        args = self._args("--condition", "refined", "--condition", "one_shot", "--condition", "oracle",
                          "--repeat", "3", "--oracle-repeat", "5")
        jobs = bc.build_jobs(scenarios, args, "m")
        counts = {}
        for job in jobs:
            counts[job["condition"]] = counts.get(job["condition"], 0) + 1
        self.assertEqual(counts, {"refined": 144, "one_shot": 120, "oracle": 40})
        keys = [bc.job_key(job) for job in jobs]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual([bc.job_key(j) for j in bc.build_jobs(scenarios, args, "m")], keys)
        other = bc.build_jobs(scenarios, self._args(
            "--condition", "refined", "--condition", "one_shot", "--condition", "oracle",
            "--repeat", "3", "--oracle-repeat", "5", "--seed", "14"), "m")
        self.assertNotEqual([bc.job_key(j) for j in other], keys)
        self.assertEqual(set(bc.job_key(j) for j in other), set(keys))
        oracle_units = {job["unit_id"] for job in jobs if job["condition"] == "oracle"}
        self.assertEqual(oracle_units, {s["base_case_id"] for s in scenarios})
        self.assertTrue(all(job["missing_count"] >= 1 for job in jobs if job["condition"] == "one_shot"))
        refined = [job for job in jobs if job["condition"] == "refined"]
        self.assertEqual(sum(1 for job in refined if job["missing_count"] == 0), 24)
        one_shot = next(job for job in jobs if job["condition"] == "one_shot")
        self.assertEqual(one_shot["input_sha256"], bc.query_digest(one_shot["query"], one_shot["options"]))
        self.assertEqual(refined[0]["input_sha256"], bc.scenario_digest(refined[0]["scenario"]))
        # Identical analysis options in every condition.
        self.assertEqual(len({json.dumps(job["options"], sort_keys=True) for job in jobs}), 1)

    def test_default_condition_and_legacy_yaml(self):
        scenarios = bc.load_scenarios(V2_YAML)
        jobs = bc.build_jobs(scenarios, bc.build_parser().parse_args(["--scenarios", str(V2_YAML)]), "m")
        self.assertEqual({job["condition"] for job in jobs}, {"refined"})
        self.assertEqual(len(jobs), 40)
        with self.assertRaises(ValueError):
            bc.build_jobs(scenarios, bc.build_parser().parse_args(
                ["--scenarios", str(V2_YAML), "--condition", "oracle"]), "m")

    def test_empty_expected_missing_only_for_k0(self):
        scenario = {
            "id": "x", "initial_query": "q", "expected_initial_missing": [],
            "clarifications": {"I": "a"}, "expected_mapping": {"I": "SPECIFIED"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps([scenario]), encoding="utf-8")
            with self.assertRaises(ValueError):
                bc.load_scenarios(path)
            path.write_text(json.dumps([dict(scenario, missing_count=0)]), encoding="utf-8")
            self.assertEqual(len(bc.load_scenarios(path)), 1)

    def test_resume_keys_require_matching_hash(self):
        scenarios = bc.load_scenarios(V3_YAML)
        args = self._args("--condition", "refined")
        job = next(j for j in bc.build_jobs(scenarios, args, "m") if j["repeat"] == 1)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            legacy = {"run_id": "r1", "scenario_id": job["unit_id"], "model": "m", "repeat": 1,
                      "scenario_sha256": job["input_sha256"], "status": "completed", "artifact_file": None}
            stale = dict(legacy, run_id="r2", scenario_id=job["unit_id"], repeat=2, scenario_sha256="old")
            failed = {"schema_version": 2, "run_id": "r3", "condition": "oracle", "model": "m",
                      "unit_id": "UC01_micro_nursery_missing_use", "repeat": 1, "input_sha256": "h",
                      "status": "error", "artifact_file": None}
            completed, latest_status, attempts = bc.resume_state([legacy, stale, failed], out, None)
            self.assertIn(bc.job_key(job), completed)
            self.assertNotIn(("refined", "m", job["unit_id"], 2, job["input_sha256"]), completed)
            self.assertEqual(latest_status[("oracle", "m", "UC01_micro_nursery_missing_use", 1)], "error")
            self.assertEqual(attempts[bc.job_key(job)], 1)
            plan = bc.select_jobs([job], args, completed, latest_status)
            self.assertEqual(plan[0][1], "cached")

    def test_dry_run_lists_jobs(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), self.assertRaises(SystemExit) as exit_info:
            bc.main(["--scenarios", str(V3_YAML), "--output", str(Path(tempfile.gettempdir()) / "murena-none"),
                     "--condition", "refined", "--condition", "one_shot", "--condition", "oracle",
                     "--repeat", "3", "--oracle-repeat", "5", "--dry-run"])
        self.assertEqual(exit_info.exception.code, 0)
        text = stream.getvalue()
        self.assertIn("total    planned= 304", text)
        self.assertIn("oracle   planned=  40", text)


class CompactionTests(unittest.TestCase):
    def test_detection_metrics(self):
        self.assertEqual(bc.detection_metrics([], []), {"precision": 1.0, "recall": 1.0, "f1": 1.0})
        self.assertEqual(bc.detection_metrics(["D"], []), {"precision": None, "recall": 0.0, "f1": 0.0})
        self.assertEqual(bc.detection_metrics([], ["D"]), {"precision": 0.0, "recall": None, "f1": 0.0})
        self.assertEqual(bc.detection_metrics(["D", "Cb"], ["D"])["f1"], round(2 / 3, 4))

    def test_extract_top_and_compact_row(self):
        buildings = [
            {"id": 1, "score": 90.0, "distance_km": 0.1, "is_match": True},
            {"id": 2, "score": 88.0, "distance_km": 0.2, "is_match": False},
            {"id": 3, "score": 85.0, "distance_km": 0.3, "is_match": True},
        ]
        self.assertEqual(bc.extract_top(buildings), [
            {"id": "1", "score": 90.0, "distance_km": 0.1}, {"id": "3", "score": 85.0, "distance_km": 0.3}])
        record = {
            "run_id": "r", "condition": "refined", "model": "m", "unit_id": "MS01_k0", "scenario_id": "MS01_k0",
            "base_case_id": "UC01", "missing_count": 0, "repeat": 1, "attempt": 1, "input_sha256": "h",
            "status": "completed", "submitted_query": "q", "final_sql": "SELECT 1", "results_count": 2,
            "clarification_seconds": 1.5, "analysis_seconds": 9.0, "artifact_file": "runs/r.json",
            "conversation": {"status": "READY", "turns": [], "initial_missing": [], "expected_initial_missing": [],
                             "missing_detection": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
                             "no_clarification": True, "mapping_accuracy": 1.0, "refined_query": "q"},
            "api_response": {
                "buildings": buildings,
                "relaxation_applied": False,
                "gemini_responses": {"fallback_activated": True},
                "agent_trace": [
                    {"agent_name": "regulatory-agent", "agent_mode": "extraction",
                     "output": {"matched_use_cases": ["Micro-nursery"], "requirements": []}},
                    {"agent_name": "sql-agent", "agent_mode": "extraction", "output": {"sql": "SELECT first"}},
                    {"agent_name": "sql-agent", "agent_mode": "extraction", "output": {"sql": "SELECT relaxed"}},
                    {"agent_name": "location-agent", "agent_mode": "extraction", "output": '{"places": []}'},
                    {"agent_name": "location-agent", "agent_mode": "ranking", "output": [{"id": "1"}]},
                ],
            },
        }
        row = bc.compact_row(record)
        self.assertEqual(row["schema_version"], bc.ROW_SCHEMA_VERSION)
        self.assertEqual([item["id"] for item in row["top"]], ["1", "3"])
        self.assertEqual(row["sql_agent_sql"], "SELECT first")
        self.assertEqual(row["matched_use_cases"], ["Micro-nursery"])
        self.assertEqual(row["extractions"]["location"], {"places": []})
        self.assertIsNone(row["extractions"]["building"])
        self.assertTrue(row["no_clarification"])
        self.assertEqual(row["turns"], 0)
        self.assertTrue(row["fallback_activated"])
        self.assertIsNone(row["relaxation_count"])
        self.assertIsNone(row["agent_errors"])
        one_shot = bc.compact_row(dict(record, condition="one_shot", conversation=None))
        self.assertIsNone(one_shot["turns"])
        self.assertIsNone(one_shot["no_clarification"])


if __name__ == "__main__":
    unittest.main()
