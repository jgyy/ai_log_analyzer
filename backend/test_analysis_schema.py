import unittest

from pydantic import ValidationError

from schemas import (
    AnalysisResult,
    BusinessSummary,
    ImmediateMitigation,
    InvestigationTimeline,
    MitigationPlan,
    RootCauseSection,
)


def minimal_analysis(**overrides):
    data = {
        "investigation_timeline": InvestigationTimeline(
            start="Logs received",
            symptom="Service errors detected",
            observation="Database connection failures appeared in logs",
            finding="Payment requests could not complete",
            root_cause="Payment service could not connect to database",
        ),
        "root_cause": RootCauseSection(
            investigation_summary="The payment service could not connect to the database.",
            impact="Customers may see failed or delayed payments.",
            root_causes=["Database connectivity failure"],
            hypotheses=[],
            key_findings=["Payment requests failed when database connections were refused"],
            investigation_gaps=[],
        ),
        "mitigation_plan": MitigationPlan(
            summary="Restore database connectivity and monitor payment transactions.",
            immediate_mitigation=ImmediateMitigation(
                prepare=[],
                pre_validate=[],
                apply=[],
                post_validate=[],
            ),
            rollback_steps=[],
            agent_spec_ready=[],
        ),
    }
    data.update(overrides)
    return AnalysisResult(**data)


class AnalysisSchemaTests(unittest.TestCase):
    def test_business_summary_is_included_in_serialized_analysis(self):
        result = minimal_analysis(
            business_summary=BusinessSummary(
                incident_title="Payment Service Disruption",
                what_happened="The payment service temporarily failed because it could not connect to the database.",
                business_impact="Customers may experience failed or delayed payments.",
                risk_level="High",
                affected_service="Payment Processing",
                recommended_next_step="Restore the affected service and monitor payment transactions.",
            )
        )

        payload = result.model_dump()

        self.assertEqual(payload["business_summary"]["incident_title"], "Payment Service Disruption")
        self.assertEqual(payload["business_summary"]["risk_level"], "High")
        self.assertEqual(payload["business_summary"]["affected_service"], "Payment Processing")

    def test_business_summary_defaults_support_existing_saved_results(self):
        result = minimal_analysis()

        self.assertEqual(result.business_summary.risk_level, "Medium")
        self.assertIn("business_summary", result.model_dump())

    def test_business_summary_rejects_unknown_risk_level(self):
        with self.assertRaises(ValidationError):
            BusinessSummary(risk_level="Severe")


if __name__ == "__main__":
    unittest.main()
