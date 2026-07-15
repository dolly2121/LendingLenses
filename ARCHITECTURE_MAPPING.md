# Architecture Mapping - the path to production

**Companion to Architecture.md. Production concerns are documented here, never built (Rules R1).**

Every component in this demo maps one to one to a production equivalent at Liberty Financial. This document is the honest answer to "how does this scale, secure, and govern" - one short section per row of Architecture.md section 2's component table.

---

## pipeline/ scripts -> Fabric pipelines and Spark notebooks

The Bronze -> Silver -> Gold batch scripts here run as plain Python against a 500-row CSV. In production, the same Medallion stages run as Fabric pipelines orchestrating Spark notebooks, sized by capacity units. **Scale**: partition Delta tables by `application_date` and replace full reloads with incremental watermark loads, so a run only ever touches new or changed data, not the whole table.

## pipeline/lake_io.py -> OneLake write patterns, table ACLs

`lake_io.append` is the sole write path here, one atomic append per call, exactly as Rules R4 requires. In production this becomes OneLake's own write patterns, with table-level ACLs replacing "only this module writes." **Security**: the AI service's production equivalent gets a managed identity on AKS with least-privilege access to only the Gold tables it needs, never a shared writer credential.

## pandera schemas -> DQ framework in Fabric

The declarative pandera checks in `silver.py` (range, uniqueness, categorical, non-null) are readable on screen deliberately. Production replaces them with Fabric's own DQ framework, but the checks themselves - the actual business rules - carry over unchanged. **Governance**: check results feed the same lineage and observability tooling described below, so a failing check is traceable to the exact pipeline run that produced it.

## Masking step in Silver -> Purview classification plus masking policy

`silver.py` hashes `customer_name` into `customer_ref_hash` with a fixed demo salt. **This demo uses a fixed salt instead of the production keyed HMAC because the demo needs deterministic, reproducible output across repeated rehearsals - a fixed salt over a small, known synthetic name pool would be reversible by dictionary attack in production, which is exactly why production never uses one.** Production classifies columns in Microsoft Purview using the same PII classes as Architecture.md section 4, and masking is enforced there as policy, not as a convention living in one Python function.

## dq_audit table -> Lineage and observability tooling

Every check, every run, one row - `dq_audit` is a minimal but real audit trail. Production captures the same information as pipeline lineage, surfaced through Purview's catalog rather than a Delta table a dashboard reads directly. **Governance**: this is also where retention rules under the Australian Privacy Principles would be enforced and audited.

## Streamlit app -> Power BI on a semantic model

The dashboard reads only Gold and audit tables, exactly as a BI tool should. Production replaces Streamlit with Power BI over a semantic model built on Gold, so business users never touch Bronze or Silver directly. **Security**: Fabric workspace RBAC separates engineering, analytics, and service-principal access to each zone.

## FastAPI service -> Containerised Python service on AKS

`ai_service/main.py` is intentionally explainable - VADER sentiment plus keyword rules, not a trained classifier, because explainable beats clever in a risk context. The production shape is the same container, running on AKS instead of a laptop. **Security**: identity via Entra ID, secrets in Azure Key Vault, encryption in transit and at rest as a platform default rather than something this demo has to set up.

## docker compose -> AKS plus CI/CD templates

`docker-compose.yml` proves the images build and run together with a shared volume standing in for a shared data layer. It is a packaging proof point, never run live on stage (Rules R1, Phases.md Phase 7). Production replaces it with AKS deployments driven by Liberty's own CI/CD templates.

## terraform/ -> Terraform with Liberty CI/CD templates

`terraform/main.tf` is one illustrative, unapplied `azurerm_key_vault` block - the production home for the masking key described above. It exists to show IaC intent, not to be run; production Terraform would be full workspace, network, and RBAC definitions driven through Liberty's own CI/CD templates, per Architecture.md section 6.

---

## Scale, in one place

Millions of rows via Delta partitioning by `application_date`, incremental watermark loads at Bronze, and Fabric Spark compute sized by capacity units. Gold aggregates become incremental merges rather than full recomputes. The Medallion pattern and the data contracts in Architecture.md section 4 do not change - only the compute underneath them does.
