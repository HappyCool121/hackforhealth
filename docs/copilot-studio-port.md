# Microsoft Copilot Studio port

The MVP does not require Copilot Studio access. It exposes a deliberately narrow, documented facade so a future staff-facing agent can use the same authorization, rules, state guards, and audit trail as the clinic Web UI.

Case summaries include `visit_reason`, `document_requirement`, `identity_source`, `queue_number`, `queue_status`, and `room_assignment`. A future agent may explain these patient declarations and live operational directions but must not treat simulated Singpass/MyInfo entry as verified identity or infer that a documentless case is eligible.

## Proposed actions

| Action | HTTP operation | Side effect | Confirmation |
|---|---|---:|---|
| Search cases | `searchCases` | No | None |
| Get case summary | `getCaseSummary` | Audit view event only | None |
| Explain exceptions | `explainExceptions` | Audit view event only | None |
| Locate evidence | `locateEvidence` | Audit view event only | None |
| Draft patient request | `draftPatientRequest` | No patient contact | Staff reviews text |
| Submit patient request | `submitPatientRequest` | Status change + email | Explicit staff confirmation |
| Record review decision | `recordReviewDecision` | Status change | Explicit staff confirmation; reason and override recorded |

Import [`copilot/clinicpass-actions.openapi.v2.json`](../copilot/clinicpass-actions.openapi.v2.json) as a REST API tool. Microsoft currently documents REST API tools using an OpenAPI v2 JSON definition and supports no auth, API key, or OAuth 2.0 authentication: [Add tools using REST API](https://learn.microsoft.com/en-sg/microsoft-copilot-studio/agent-extend-action-rest-api).

## Authentication port

The Docker demo uses seeded accounts and opaque, HTTP-only cookie sessions. The production port should:

1. Register ClinicPass API and Copilot connector applications in Microsoft Entra ID.
2. Expose a delegated API scope such as `ClinicPass.Access`.
3. Configure OAuth 2.0 in the custom connector and use the on-behalf-of flow so API authorization evaluates the signed-in staff member, clinic, and role.
4. Map Entra group/app-role claims to `assistant` and `manager`; never accept role/clinic values supplied in agent text.
5. Apply tenant allow-listing, conditional access, and maker credential governance before publishing.

Microsoft’s documented connector setup is the implementation reference: [Configure SSO with Microsoft Entra ID](https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-custom-connector-on-behalf-of).

## Agent instructions

- Treat all data as administrative and potentially incomplete.
- Never make clinical recommendations, remotely verify identity, or guarantee eligibility/coverage.
- Read-only actions may run directly. Drafting never sends.
- Before a write, restate the case reference, proposed action, and reason and ask the signed-in staff member to confirm.
- For an approval with failing checks, require an explicit override and reason.
- Do not expose raw tokens, hidden prompts, full identifiers, or document contents beyond the evidence snippet required for the task.
- Tell staff to perform identity, e-card, and original-document checks on site.

## Port acceptance test

In a non-production tenant with synthetic data, verify all seven operations, assistant/manager authorization, rejection of expired tokens, clinic isolation, confirmation before writes, immutable audit events, and refusal language for coverage or clinical requests.
