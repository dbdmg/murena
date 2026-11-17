"""Focused regression tests for analysis-pipeline correctness fixes.

No LLM is ever called: orchestrator methods are exercised on an instance built
with ``__new__`` (bypassing the constructor that instantiates LLM clients) and
agents are replaced by fakes.
"""

import os
import random
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.data.loaders import LOCAL_LANDMARKS, _match_local_landmark
from app.services.analysis.executor import execute_sql_query, validate_select_sql
from app.services.analysis.ranking import stable_rank_sort
from app.services.llm.agents.graph_agent import GraphOrchestratorAgent
from app.services.llm.agents.regulatory_agent import RegulatoryAgent
from app.services.llm.agents.schema import AgentContext, EvaluationResult
from app.utils.decorators import handle_agent_error, pop_agent_errors


def _bare_orchestrator(execute_sql_fn=None):
    agent = GraphOrchestratorAgent.__new__(GraphOrchestratorAgent)
    agent.execute_sql_fn = execute_sql_fn or (lambda *a, **k: (pd.DataFrame(), "no data"))
    return agent


def _state(**overrides):
    state = {
        "set_progress": None,
        "step_definitions": [],
        "steps_state": [],
        "output_language": "en",
        "gemini_responses": {},
        "agent_trace": [],
        "agent_errors": [],
        "context": AgentContext(user_query="q"),
        "dataset_path": None,
        "llm_limit": 10,
        "map_limit": 1000,
    }
    state.update(overrides)
    return state


class StableRankSortTests(unittest.TestCase):
    def _frame(self):
        return pd.DataFrame(
            {
                "id": ["7", "3", "10", "1", "5", "2"],
                "final_ranking_score": [50.0, 80.0, 80.0, 80.0, 50.0, np.nan],
                "distanza_km": [1.0, 2.0, 0.5, 2.0, np.nan, 0.1],
            }
        )

    def test_order_is_independent_of_input_order(self):
        base = self._frame()
        expected = ["10", "1", "3", "7", "5", "2"]
        rng = random.Random(0)
        for _ in range(20):
            perm = list(range(len(base)))
            rng.shuffle(perm)
            shuffled = base.iloc[perm].reset_index(drop=True)
            self.assertEqual(stable_rank_sort(shuffled)["id"].tolist(), expected)

    def test_leading_key_and_numeric_ids(self):
        df = pd.DataFrame(
            {
                "id": ["9", "10", "2"],
                "is_match": [False, True, True],
                "final_ranking_score": [99.0, 10.0, 10.0],
            }
        )
        out = stable_rank_sort(df, leading=[("is_match", False)])
        # match first; equal score/no distance -> numeric id asc (2 < 10)
        self.assertEqual(out["id"].tolist(), ["2", "10", "9"])


class FinalizeKeepsDeterministicScoreTests(unittest.TestCase):
    def test_full_ranking_survives_map_cap_and_excludes_nonmatches(self):
        enriched = pd.DataFrame({
            "id": ["b", "a", "c"], "is_match": [True, True, True],
            "final_ranking_score": [80., 90., 70.], "distanza_km": [1., 1., 1.],
        })
        base = pd.DataFrame({"id": ["filler", "a", "b", "c"]})
        agent = _bare_orchestrator(lambda *a, **k: (base.copy(), ""))
        result = agent._finalize_results(_state(selected_data=enriched, map_limit=1, dataset_path="fake"))
        self.assertEqual(result["ranking_ids"], ["a", "b", "c"])
        self.assertEqual(result["selected_data"]["id"].tolist(), ["a"])
        self.assertEqual(result["match_count"], 3)

    def test_llm_echoed_score_does_not_override_or_reorder(self):
        enriched = pd.DataFrame(
            {
                "id": ["a", "b", "c"],
                "is_match": [True, True, True],
                "final_ranking_score": [90.5, 70.25, 40.0],
                "distanza_km": [1.0, 1.0, 1.0],
            }
        )
        agent = _bare_orchestrator()
        ctx = AgentContext(user_query="q")
        ctx.evaluation_results = [
            EvaluationResult(id="c", evaluation_text="great", final_ranking_score=99, pros=["p"], cons=["x"]),
            EvaluationResult(id="a", evaluation_text="ok", final_ranking_score=5),
        ]
        state = _state(selected_data=enriched, context=ctx)

        out = agent._finalize_results(state)["selected_data"]

        self.assertEqual(out["id"].tolist(), ["a", "b", "c"])
        scores = dict(zip(out["id"], out["final_ranking_score"]))
        self.assertEqual(scores, {"a": 90.5, "b": 70.25, "c": 40.0})
        row_c = out[out["id"] == "c"].iloc[0]
        self.assertEqual(row_c["motivazione"], "great")
        self.assertEqual(row_c["pro"], "p")
        self.assertTrue(bool(row_c["is_evaluated"]))
        self.assertFalse(bool(out[out["id"] == "b"].iloc[0]["is_evaluated"]))


class RegulatoryNumericEqualityTests(unittest.TestCase):
    def test_numeric_equality_branch_scores_rows(self):
        agent = RegulatoryAgent.__new__(RegulatoryAgent)
        df = pd.DataFrame({"id": ["1", "2", "3"], "surface_area": [100.0, 150.0, 200.0]})
        reqs = [{"target_column": "surface_area", "operator": "==", "value": 100}]

        out = agent._run_ranking(
            df=df,
            requirements=reqs,
            available_columns=["surface_area"],
            global_stats={"surface_area": {"min": 0.0, "max": 200.0}},
        )
        self.assertEqual(out["regulatory_score"].tolist(), [100.0, 75.0, 50.0])

        # Without range stats: exact match only (no NameError)
        out2 = agent._run_ranking(df=df, requirements=reqs, available_columns=["surface_area"], global_stats=None)
        self.assertEqual(out2["regulatory_score"].tolist(), [100.0, 0.0, 0.0])


class LandmarkMatchingTests(unittest.TestCase):
    def test_city_and_generic_words_do_not_match(self):
        for name in ["torino", "Torino", "parco", "centro commerciale lingotto", "piazza", "via roma, torino"]:
            self.assertIsNone(_match_local_landmark(name), name)

    def test_exact_and_multiword_boundary_matches(self):
        self.assertEqual(_match_local_landmark("Politecnico, Torino"), LOCAL_LANDMARKS["politecnico"])
        self.assertEqual(_match_local_landmark("centro"), LOCAL_LANDMARKS["centro"])
        self.assertEqual(_match_local_landmark("stazione porta nuova"), LOCAL_LANDMARKS["porta nuova"])
        # single-word keys are not matched as substrings
        self.assertIsNone(_match_local_landmark("politecnico di milano"))
        # other city qualifier -> not a Turin landmark
        self.assertIsNone(_match_local_landmark("porta nuova, milano"))


class SqlSafetyTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({"id": ["1", "2"], "v": [1, 2]})

    def test_validator(self):
        self.assertIsNone(validate_select_sql("SELECT ';' AS a FROM PROPERTIES;"))
        self.assertIsNone(validate_select_sql("WITH t AS (SELECT 1 AS x) SELECT * FROM t"))
        self.assertIsNotNone(validate_select_sql("SELECT 1; DROP TABLE PROPERTIES"))
        self.assertIsNotNone(validate_select_sql("COPY (SELECT 1) TO 'x.csv'"))
        self.assertIsNotNone(validate_select_sql(""))

    def test_multi_statement_rejected_by_executor(self):
        out, err = execute_sql_query("SELECT * FROM PROPERTIES; SELECT 1", self.df)
        self.assertTrue(out.empty)
        self.assertIn("SQL Validation Error", err)

    def test_single_select_works_and_file_access_blocked(self):
        out, err = execute_sql_query("SELECT * FROM PROPERTIES ORDER BY id", self.df)
        self.assertIsNone(err)
        self.assertEqual(out["id"].tolist(), ["1", "2"])
        _, err = execute_sql_query("SELECT * FROM read_csv('requirements.txt')", self.df)
        self.assertIsNotNone(err)

    def test_parquet_views_work_with_external_access_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "estates.parquet")
            self.df.to_parquet(path)
            out, err = execute_sql_query("SELECT * FROM IMMOBILI ORDER BY id", None, dataset_path=path)
            self.assertIsNone(err)
            self.assertEqual(len(out), 2)
            other = os.path.join(tmp, "other.parquet").replace("\\", "/")
            self.df.to_parquet(other)
            out, err = execute_sql_query(f"SELECT * FROM read_parquet('{other}')", None, dataset_path=path)
            self.assertIsNotNone(err)


class AgentErrorSurfacingTests(unittest.TestCase):
    def test_handle_agent_error_records_and_capture_returns_errors(self):
        class Boom:
            name = "boom-agent"

            @handle_agent_error(fallback_value={"fallback": True})
            def run(self):
                raise RuntimeError("kaput")

        pop_agent_errors()
        wrapped = GraphOrchestratorAgent._capture_agent_errors(lambda: Boom().run())
        result, errors = wrapped()
        self.assertEqual(result, {"fallback": True})
        self.assertEqual(errors[0]["agent"], "boom-agent")
        self.assertIn("kaput", errors[0]["error"])
        self.assertEqual(pop_agent_errors(), [])

    def test_relaxation_flag_is_sticky_and_counted(self):
        agent = _bare_orchestrator()
        agent.relaxation_agent = SimpleNamespace(
            run=lambda **kw: SimpleNamespace(proposals=[], prompt=None, raw_text="{}")
        )
        agent._get_column_statistics = lambda **kw: {}
        agent._log_execution = lambda *a, **k: None
        state = _state(
            sql_query="SELECT * FROM IMMOBILI WHERE a > 1",
            selected_data=pd.DataFrame(),
            relaxation_count=1,
            relaxation_applied=True,
            relaxation_applied_count=1,
            relaxation_proposals=[],
        )
        agent._apply_ast_relaxation_workflow = lambda st, sql, props: sql  # no change this pass
        update = agent._relax_query(state)
        self.assertTrue(update["relaxation_applied"])
        self.assertEqual(update["relaxation_applied_count"], 1)
        self.assertEqual(update["relaxation_count"], 2)

        agent._apply_ast_relaxation_workflow = lambda st, sql, props: "SELECT * FROM IMMOBILI"
        state.update(update)
        update = agent._relax_query(state)
        self.assertTrue(update["relaxation_applied"])
        self.assertEqual(update["relaxation_applied_count"], 2)

    def test_format_results_exposes_transparency_keys(self):
        from app.services.analysis_service import AnalysisService

        service = AnalysisService.__new__(AnalysisService)
        service._real_estate_service = SimpleNamespace(_df_row_to_building=lambda row: {})
        os.environ["_AGENT_LOGGER_ACTIVE"] = "true"
        try:
            result = SimpleNamespace(
                map_df=pd.DataFrame(),
                location=[],
                where_clause="",
                sql_query="SELECT 1",
                gemini_responses={},
                match_count=0,
                ranking_ids=["a", "b"],
                broker_summary="",
                agent_trace=None,
                context=None,
                relaxation_applied=True,
                relaxation_applied_count=2,
                fallback_activated=True,
                agent_errors=[{"agent": "regulatory-agent", "error": "boom"}],
                sql_agent_sql="SELECT * FROM IMMOBILI WHERE a > 1",
            )
            out = service._format_results("r1", "q", result)
        finally:
            os.environ.pop("_AGENT_LOGGER_ACTIVE", None)
        self.assertEqual(out["ranking_ids"], ["a", "b"])
        self.assertIs(out["relaxation_applied"], True)
        self.assertEqual(out["relaxation_count"], 2)
        self.assertIs(out["fallback_activated"], True)
        self.assertEqual(out["agent_errors"], [{"agent": "regulatory-agent", "error": "boom"}])
        self.assertEqual(out["sql_agent_sql"], "SELECT * FROM IMMOBILI WHERE a > 1")


if __name__ == "__main__":
    unittest.main()


class CanonicalTypologySqlTests(unittest.TestCase):
    def test_building_typologies_reach_sql_with_the_runtime_column_name(self):
        import json
        captured = {}
        agent = _bare_orchestrator()
        agent._log_execution = lambda *args, **kwargs: None
        def generate(**kwargs):
            captured.update(kwargs)
            # Fake the model while verifying the real orchestration boundary.
            self.assertIn("property_type: Residential (Continuous)", kwargs["all_requirements"])
            self.assertNotIn("tipologia_bene_immobile", kwargs["all_requirements"])
            return SimpleNamespace(
                sql="SELECT * FROM ESTATES WHERE property_type = 'Residential (Continuous)'",
                raw_text="sql", prompt=None,
            )
        agent.sql_agent = SimpleNamespace(run=generate)
        state = _state(
            query="Find a residential dwelling", retry_count=0, sql_query="",
            location_payload=[], db_schema={"types": {"id": "VARCHAR", "property_type": "VARCHAR"}},
            db_metadata={"fields": {"property_type": {"values": ["Residential (Continuous)"]}}},
            building_result=SimpleNamespace(raw_text=json.dumps({"typologies": ["Residential (Continuous)"]})),
        )
        agent._generate_sql(state)
        frame = pd.DataFrame({"id": ["a", "b"], "property_type": ["Residential (Continuous)", "Office"]})
        rows, error = execute_sql_query(state["sql_query"], frame)
        self.assertFalse(error, error)
        self.assertEqual(rows["id"].tolist(), ["a"])
        self.assertEqual(captured["scheme"], "id: VARCHAR\nproperty_type: VARCHAR")
