"""Unit tests for the IntentPlanner keyword fallback."""

from logos.analyst.planner import IntentPlanner


class TestIntentPlannerKeyword:
    def test_economy_keywords(self):
        p = IntentPlanner(metis_url=None)  # force keyword fallback
        plan = p._plan_keyword("how much money is in the treasury?")
        assert plan["intent"] == "economy"
        assert "treasury" in plan["sources"]

    def test_security_keywords(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("are there any critical findings from MOMUS?")
        assert plan["intent"] == "security"
        assert "momus" in plan["sources"]

    def test_latency_keywords(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("why is the hub so slow?")
        assert plan["intent"] == "latency"

    def test_reputation_keywords(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("who is the most trusted hub?")
        assert plan["intent"] == "reputation"

    def test_general_fallback(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("hello how are you doing today")
        assert plan["intent"] == "general"

    def test_russian_keywords(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("сколько денег в казначействе")
        assert plan["intent"] == "economy"

    def test_russian_ui_chips(self):
        """Exact RU suggestion chips from logos/frontend i18n must classify."""
        p = IntentPlanner(metis_url=None)
        assert p._plan_keyword("На сколько хватит казначейства?")["intent"] == "economy"
        assert p._plan_keyword("Есть критические находки?")["intent"] == "security"
        assert p._plan_keyword("Какие хабы тормозят?")["intent"] == "latency"
        assert p._plan_keyword("Кто самый надёжный хаб?")["intent"] == "reputation"
        assert p._plan_keyword("Дай обзор федерации")["intent"] == "general"

    def test_english_ui_chips(self):
        p = IntentPlanner(metis_url=None)
        assert p._plan_keyword("How long will the Treasury last?")["intent"] == "economy"
        assert p._plan_keyword("Are there any critical findings?")["intent"] == "security"
        assert p._plan_keyword("Which hubs are slow right now?")["intent"] == "latency"
        assert p._plan_keyword("Who is the most trusted hub?")["intent"] == "reputation"

    def test_spanish_keywords(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("cuánto dinero hay en la tesorería")
        assert plan["intent"] == "economy"

    def test_spanish_ui_chips(self):
        p = IntentPlanner(metis_url=None)
        assert p._plan_keyword("¿Cuánto durará la Tesorería?")["intent"] == "economy"
        assert p._plan_keyword("¿Hay hallazgos críticos?")["intent"] == "security"
        assert p._plan_keyword("¿Qué hubs están lentos?")["intent"] == "latency"
        assert p._plan_keyword("¿Cuál es el hub más confiable?")["intent"] == "reputation"

    def test_french_ui_chips(self):
        p = IntentPlanner(metis_url=None)
        assert p._plan_keyword("Combien de temps durera la trésorerie ?")["intent"] == "economy"
        assert p._plan_keyword("Y a-t-il des constats critiques ?")["intent"] == "security"
        assert p._plan_keyword("Quels hubs sont lents actuellement ?")["intent"] == "latency"
        assert p._plan_keyword("Quel est le hub le plus fiable ?")["intent"] == "reputation"

    def test_chinese_ui_chips(self):
        p = IntentPlanner(metis_url=None)
        assert p._plan_keyword("国库还能维持多久？")["intent"] == "economy"
        assert p._plan_keyword("有严重发现吗？")["intent"] == "security"
        assert p._plan_keyword("哪些枢纽变慢了？")["intent"] == "latency"
        assert p._plan_keyword("哪个枢纽最受信任？")["intent"] == "reputation"

    def test_metis_used_flag(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("test")
        assert plan["metis_used"] is False

    def test_keyword_fallback_confidence(self):
        p = IntentPlanner(metis_url=None)
        plan = p._plan_keyword("treasury balance please")
        assert plan["confidence"] == 0.6  # keyword fallback always 0.6

    def test_validate_intent(self):
        assert IntentPlanner._validate_intent("economy") == "economy"
        assert IntentPlanner._validate_intent("nonsense") == "general"
