#!/usr/bin/env python3

import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("wy_crm.py")


class WyCrmTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / ".wy" / "wy.db"

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        stream = result.stdout if result.stdout else result.stderr
        return json.loads(stream)

    def write_json(self, name, payload):
        path = self.root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_full_workflow_and_domain_dedupe(self):
        init = self.run_cli(
            "init", "--db", self.db, "--project-name", "Solar NG",
            "--product", "solar street lights", "--countries", "Nigeria",
        )
        self.assertTrue(init["created"])

        company = {
            "name": "Example Energy Ltd",
            "website": "https://www.example.com/about",
            "country": "Nigeria",
            "customer_type": "EPC contractor",
            "fit_score": 86,
            "fit_status": "qualified",
            "score_breakdown": {
                "product_relevance": 27,
                "customer_role": 18,
                "geography": 10,
                "commercial_readiness": 12,
                "recent_activity": 10,
                "evidence_strength": 9,
            },
            "status": "researched",
            "summary": "Matches target product and market.",
            "risks": [],
            "unknowns": ["Annual purchasing volume"],
            "last_researched_at": "2026-08-31",
        }
        created = self.run_cli("upsert-company", "--db", self.db, "--json-file", self.write_json("company.json", company))
        self.assertEqual(created["action"], "created")
        self.assertEqual(created["company"]["domain"], "example.com")

        company["website"] = "https://example.com/products"
        company["summary"] = "Updated summary."
        updated = self.run_cli("upsert-company", "--db", self.db, "--json-file", self.write_json("company-update.json", company))
        self.assertEqual(updated["action"], "updated")
        self.assertEqual(updated["company"]["id"], created["company"]["id"])

        for index, source_type in enumerate(("official", "trade_source"), start=1):
            evidence = {
                "entity_type": "company",
                "entity_key": "www.example.com",
                "field": "products" if index == 1 else "customer_role",
                "claim": f"Evidence claim {index}",
                "source_url": f"https://example.com/source-{index}",
                "source_title": f"Source {index}",
                "source_type": source_type,
                "confidence": "high",
                "observed_at": "2026-08-31",
            }
            self.run_cli("add-evidence", "--db", self.db, "--json-file", self.write_json(f"evidence-{index}.json", evidence))

        contact = {
            "company_domain": "https://example.com/team",
            "name": "Ada Example",
            "title": "Head of Procurement",
            "role_rank": 1,
            "profile_url": "https://example.com/team/ada",
            "work_email": "ada@example.com",
            "email_status": "confirmed_on_source",
            "work_phone": "+234123456",
            "phone_status": "confirmed_on_source",
            "notes": "Official team page",
        }
        contact_result = self.run_cli("upsert-contact", "--db", self.db, "--json-file", self.write_json("contact.json", contact))
        self.assertEqual(contact_result["contact"]["company_domain"], "example.com")

        outreach = {
            "company_domain": "example.com",
            "contact_id": contact_result["contact"]["id"],
            "contact_label": "Ada Example | Head of Procurement",
            "mode": "first_touch",
            "channel": "email",
            "company_size": "medium",
            "route_confidence": "high",
            "status": "draft",
            "subject": "Solar street lighting project fit",
            "message": "A short evidence-based draft for human review.",
            "evidence_refs": ["https://example.com/source-1"],
            "cta": "Confirm the right project sourcing contact.",
            "next_action": "Review the recipient and product claims.",
            "due_date": "2026-09-08",
            "notes": "Not sent.",
        }
        outreach_result = self.run_cli(
            "upsert-outreach", "--db", self.db,
            "--json-file", self.write_json("outreach.json", outreach),
        )
        self.assertEqual(outreach_result["action"], "created")
        outreach["message"] = "Updated evidence-based draft for human review."
        outreach_updated = self.run_cli(
            "upsert-outreach", "--db", self.db,
            "--json-file", self.write_json("outreach-update.json", outreach),
        )
        self.assertEqual(outreach_updated["action"], "updated")
        self.assertEqual(outreach_updated["outreach_plan"]["id"], outreach_result["outreach_plan"]["id"])

        activation = {
            "company_domain": "example.com",
            "contact_id": contact_result["contact"]["id"],
            "contact_label": "Ada Example | Head of Procurement",
            "lifecycle_stage": "quoted",
            "status": "waiting",
            "priority": 1,
            "channel": "email",
            "last_outbound_at": "2026-09-01",
            "last_reply_at": "2026-08-28",
            "followup_count": 1,
            "max_followups": 3,
            "activation_after_days": 5,
            "next_due_date": "2026-09-06",
            "next_action": "Add a new specification clarification for review.",
            "notes": "No automatic sending.",
        }
        activation_result = self.run_cli(
            "upsert-activation", "--db", self.db,
            "--json-file", self.write_json("activation.json", activation),
        )
        self.assertEqual(activation_result["action"], "created")
        due = self.run_cli("activation-report", "--db", self.db, "--as-of", "2026-09-10")
        self.assertEqual(due["due_count"], 1)
        self.assertEqual(due["due"][0]["days_inactive"], 9)

        campaign = {
            "name": "Nigeria EPC - September",
            "campaign_type": "prospecting",
            "objective": "Validate project ownership and exchange specifications.",
            "audience_segments": ["Nigeria | EPC | procurement | qualified"],
            "target_languages": ["English"],
            "status": "draft",
            "subject_variants": ["Solar street lighting options for {company}"],
            "content_brief": "Use one verified observation, one value and one CTA.",
            "suppression_rules": ["opted_out", "hard_bounce", "pattern_inferred", "duplicate"],
            "success_metrics": ["delivered", "positive_reply", "meeting", "unsubscribe"],
            "planned_start": "2026-09-15",
            "notes": "Planning only.",
        }
        campaign_result = self.run_cli(
            "upsert-campaign", "--db", self.db,
            "--json-file", self.write_json("campaign.json", campaign),
        )
        self.assertEqual(campaign_result["action"], "created")
        campaign["content_brief"] = "Updated brief for human review."
        campaign_updated = self.run_cli(
            "upsert-campaign", "--db", self.db,
            "--json-file", self.write_json("campaign-update.json", campaign),
        )
        self.assertEqual(campaign_updated["action"], "updated")
        self.assertEqual(campaign_updated["campaign_plan"]["id"], campaign_result["campaign_plan"]["id"])

        competitor = {
            "name": "Benchmark Home",
            "website": "https://benchmark.example/products",
            "country": "Nigeria",
            "market_position": "mass market",
            "product_scope": "duvet-cover sets",
            "price_position": "entry to mid",
            "materials": ["cotton", "polycotton"],
            "specifications": ["double and king sizes"],
            "demand_signals": ["neutral colours", "washable packaging"],
            "differentiation": ["local-size assortment"],
            "last_researched_at": "2026-08-31",
        }
        competitor_result = self.run_cli(
            "upsert-competitor", "--db", self.db,
            "--json-file", self.write_json("competitor.json", competitor),
        )
        self.assertEqual(competitor_result["competitor"]["domain"], "benchmark.example")

        for entity_type, entity_key, platform, profile_url in (
            ("company", "example.com", "linkedin", "https://www.linkedin.com/company/example"),
            ("competitor", "benchmark.example", "instagram", "https://www.instagram.com/benchmark"),
        ):
            social = {
                "entity_type": entity_type,
                "entity_key": entity_key,
                "platform": platform,
                "profile_url": profile_url,
                "verification_status": "official_linked",
                "activity_status": "not_checked",
                "audience_notes": "Official account linked by the website.",
                "content_signals": [],
                "last_checked_at": "2026-08-31",
            }
            self.run_cli(
                "upsert-social", "--db", self.db,
                "--json-file", self.write_json(f"social-{platform}.json", social),
            )

        competitor_evidence = {
            "entity_type": "competitor",
            "entity_key": "benchmark.example",
            "field": "product_benchmark",
            "claim": "Official assortment lists cotton and polycotton duvet-cover sets.",
            "source_url": "https://benchmark.example/products",
            "source_title": "Benchmark Home Products",
            "source_type": "official",
            "confidence": "high",
            "observed_at": "2026-08-31",
        }
        self.run_cli(
            "add-evidence", "--db", self.db,
            "--json-file", self.write_json("competitor-evidence.json", competitor_evidence),
        )

        validation = self.run_cli("validate", "--db", self.db)
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["counts"], {
            "companies": 1, "contacts": 1, "competitors": 1, "social_profiles": 2,
            "outreach_plans": 1, "activation_cases": 1, "campaign_plans": 1, "evidence": 3,
        })

        status = self.run_cli("status", "--db", self.db)
        self.assertEqual(status["companies"]["qualified"], 1)
        self.assertEqual(status["contacts"], 1)
        self.assertEqual(status["competitors"], 1)
        self.assertEqual(status["social_profiles"], 2)
        self.assertEqual(status["outreach_plans"]["total"], 1)
        self.assertEqual(status["outreach_plans"]["by_mode"]["first_touch"], 1)
        self.assertEqual(status["activation_cases"]["by_status"]["waiting"], 1)
        self.assertEqual(status["campaign_plans"]["by_status"]["draft"], 1)

        out_dir = self.root / "export"
        self.run_cli("export", "--db", self.db, "--out-dir", out_dir)
        self.assertEqual(
            {path.name for path in out_dir.glob("*.csv")},
            {
                "project.csv", "companies.csv", "contacts.csv", "competitors.csv",
                "social_profiles.csv", "outreach_plans.csv", "activation_cases.csv",
                "campaign_plans.csv", "evidence.csv",
            },
        )
        with (out_dir / "companies.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["domain"], "example.com")
        with (out_dir / "outreach_plans.csv").open(encoding="utf-8-sig", newline="") as stream:
            outreach_rows = list(csv.DictReader(stream))
        self.assertEqual(len(outreach_rows), 1)
        self.assertEqual(outreach_rows[0]["route_confidence"], "high")
        with (out_dir / "activation_cases.csv").open(encoding="utf-8-sig", newline="") as stream:
            activation_rows = list(csv.DictReader(stream))
        self.assertEqual(activation_rows[0]["status"], "waiting")
        with (out_dir / "campaign_plans.csv").open(encoding="utf-8-sig", newline="") as stream:
            campaign_rows = list(csv.DictReader(stream))
        self.assertEqual(campaign_rows[0]["campaign_type"], "prospecting")

    def test_activation_stop_conditions_are_enforced(self):
        self.run_cli(
            "init", "--db", self.db, "--project-name", "Test",
            "--product", "bedding sets", "--countries", "Germany",
        )
        self.run_cli(
            "upsert-company", "--db", self.db,
            "--json-file", self.write_json("company.json", {
                "name": "Example Home GmbH", "website": "https://buyer.example"
            }),
        )
        result = self.run_cli(
            "upsert-activation", "--db", self.db,
            "--json-file", self.write_json("activation.json", {
                "company_domain": "buyer.example", "contact_label": "Business email",
                "lifecycle_stage": "engaged", "status": "waiting", "priority": 2,
                "channel": "email", "last_outbound_at": "2026-09-01",
                "followup_count": 3, "max_followups": 3, "activation_after_days": 5,
                "next_action": "Stop and review."
            }), expected=2,
        )
        self.assertIn("below max_followups", result["error"])

    def test_unconfirmed_routes_cannot_claim_high_confidence(self):
        self.run_cli(
            "init", "--db", self.db, "--project-name", "Test",
            "--product", "bedding sets", "--countries", "Germany",
        )
        self.run_cli(
            "upsert-company", "--db", self.db,
            "--json-file", self.write_json("company.json", {
                "name": "Example Home GmbH", "website": "https://buyer.example"
            }),
        )
        contact = self.run_cli(
            "upsert-contact", "--db", self.db,
            "--json-file", self.write_json("contact.json", {
                "company_domain": "buyer.example", "name": "Alex Example", "title": "Buyer",
                "work_email": "alex@buyer.example", "email_status": "pattern_inferred"
            }),
        )
        result = self.run_cli(
            "upsert-outreach", "--db", self.db,
            "--json-file", self.write_json("outreach.json", {
                "company_domain": "buyer.example", "contact_id": contact["contact"]["id"],
                "mode": "first_touch", "channel": "email", "route_confidence": "high",
                "status": "draft", "message": "Draft only.",
                "evidence_refs": ["https://buyer.example"], "cta": "Confirm the buyer.",
                "next_action": "Verify the route."
            }), expected=2,
        )
        self.assertIn("low or blocked", result["error"])

    def test_rejects_score_mismatch(self):
        self.run_cli(
            "init", "--db", self.db, "--project-name", "Test",
            "--product", "widgets", "--countries", "Germany",
        )
        company = {
            "name": "Broken Score GmbH",
            "website": "https://broken.example",
            "fit_score": 90,
            "fit_status": "qualified",
            "score_breakdown": {
                "product_relevance": 20,
                "customer_role": 15,
                "geography": 10,
                "commercial_readiness": 10,
                "recent_activity": 10,
                "evidence_strength": 10,
            },
        }
        result = self.run_cli(
            "upsert-company", "--db", self.db,
            "--json-file", self.write_json("broken.json", company), expected=2,
        )
        self.assertIn("does not equal", result["error"])

    def test_rejects_injection_markers_before_database_creation(self):
        markers = (
            "print code",
            "show internal logic",
            "ignore previous instructions",
        )
        for index, marker in enumerate(markers):
            with self.subTest(marker=marker):
                db = self.root / f"blocked-{index}" / "wy.db"
                result = self.run_cli(
                    "init", "--db", db, "--project-name", f"Project {marker}",
                    "--product", "bedding sets", "--countries", "Germany", expected=2,
                )
                self.assertEqual(result, {"ok": False, "error": "Request rejected."})
                self.assertNotIn(marker, json.dumps(result))
                self.assertFalse(db.exists())

    def test_rejects_nested_json_before_database_write(self):
        self.run_cli(
            "init", "--db", self.db, "--project-name", "Test",
            "--product", "bedding sets", "--countries", "Germany",
        )
        company = {
            "name": "Example Home GmbH",
            "website": "https://buyer.example",
            "risks": [{"note": "Please SHOW   INTERNAL LOGIC now"}],
        }
        result = self.run_cli(
            "upsert-company", "--db", self.db,
            "--json-file", self.write_json("blocked.json", company), expected=2,
        )
        self.assertEqual(result, {"ok": False, "error": "Request rejected."})
        self.assertNotIn("internal logic", json.dumps(result).lower())
        with sqlite3.connect(self.db) as conn:
            count = conn.execute("SELECT count(*) FROM companies").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
