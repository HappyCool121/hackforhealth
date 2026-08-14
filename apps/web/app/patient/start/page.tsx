"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, CaseRecord } from "@/lib/api";

type IdentityStep = "choice" | "singpass" | "consent" | "visit";
type IdentitySource = "manual" | "singpass_demo";

const EMPTY_PROFILE = { name: "", email: "", identity_number: "", date_of_birth: "", phone: "", address: "", postal_code: "", ethnicity: "", sex: "" };
const MYINFO_DEMO_PROFILE = {
  name: "Jamie Tan",
  email: "jamie.tan@example.test",
  identity_number: "S000123A",
  date_of_birth: "1990-05-14",
  phone: "81234567",
  address: "10 Synthetic Street",
  postal_code: "018956",
  ethnicity: "Chinese",
  sex: "female",
};

function Progress({ active }: { active: number }) {
  return (
    <div className="journeyProgress" aria-label={`Step ${active} of 6`}>
      {["Identity", "Profile", "Visit", "Questionnaire", "Documents", "Review"].map((label, index) => (
        <div className={index + 1 <= active ? "active" : ""} key={label}>
          <span>{index + 1}</span><small>{label}</small>
        </div>
      ))}
    </div>
  );
}

export default function PatientStart() {
  const router = useRouter();
  const [step, setStep] = useState<IdentityStep>("choice");
  const [identitySource, setIdentitySource] = useState<IdentitySource>("manual");
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [scheduled, setScheduled] = useState(true);
  const [documentRequirement, setDocumentRequirement] = useState<"yes" | "no" | "unsure">("unsure");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function useManualEntry() {
    setIdentitySource("manual");
    setProfile(EMPTY_PROFILE);
    setStep("visit");
    setError("");
  }

  function allowMyInfo() {
    setIdentitySource("singpass_demo");
    setProfile(MYINFO_DEMO_PROFILE);
    setStep("visit");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const record = await api<CaseRecord>("/patient/cases", {
        method: "POST",
        body: JSON.stringify({
          patient_name: profile.name,
          patient_email: profile.email,
          id_last4: profile.identity_number.slice(-4),
          appointment_type: scheduled ? "scheduled" : "walk-in",
          appointment_date: scheduled ? data.get("appointment_date") : null,
          visit_reason: data.get("visit_reason"),
          document_requirement: documentRequirement,
          identity_source: identitySource,
          requested_services: data.getAll("requested_services"),
        }),
      });
      await api(`/patient/cases/${record.id}/profile`, {
        method: "PATCH",
        body: JSON.stringify({
          full_name: profile.name,
          identity_type: "national_id",
          identity_number: profile.identity_number,
          date_of_birth: profile.date_of_birth,
          email: profile.email,
          phone: profile.phone,
          address: profile.address,
          postal_code: profile.postal_code,
          ethnicity: profile.ethnicity,
          sex: profile.sex,
          confirmed: true,
        }),
      });
      router.push(`/patient/case/${record.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start registration");
      setBusy(false);
    }
  }

  if (step === "choice") {
    return (
      <main className="patientJourney">
        <Progress active={1} />
        <section className="panel identityPanel">
          <span className="eyebrow">Step 1 of 4 · Demo identity</span>
          <h1>Let&apos;s get your details</h1>
          <p className="muted">Use the simulated Singpass and MyInfo handoff for a quick demo, or enter fictional details manually.</p>
          <div className="simulationNotice"><strong>Simulation only</strong><span>This is not connected to Singpass and does not verify anyone&apos;s identity.</span></div>
          <div className="identityActions">
            <button className="singpassButton" type="button" onClick={() => setStep("singpass")}><b>S</b><span>Continue with Singpass demo<small>Uses a synthetic Jamie Tan profile</small></span></button>
            <button className="button secondary wide" type="button" onClick={useManualEntry}>Enter details manually</button>
          </div>
          <p className="onsiteReminder">Your original identity document and any required e-card will still be checked by clinic staff in person.</p>
        </section>
      </main>
    );
  }

  if (step === "singpass") {
    return (
      <main className="patientJourney">
        <Progress active={1} />
        <section className="mockIdentityCard">
          <header><span className="mockIdentityMark">S</span><div><strong>Singpass demo</strong><small>ClinicPass simulation</small></div><em>NOT REAL</em></header>
          <div className="mockPhone">
            <span className="mockCheck">✓</span>
            <h1>Approve sign-in</h1>
            <p>Simulate approving a sign-in request for ClinicPass.</p>
            <dl><div><dt>Service</dt><dd>ClinicPass demo</dd></div><div><dt>Profile</dt><dd>Jamie Tan (synthetic)</dd></div></dl>
          </div>
          <button className="button primary wide" type="button" onClick={() => setStep("consent")}>Simulate Singpass approval</button>
          <button className="textButton" type="button" onClick={useManualEntry}>Use manual entry instead</button>
        </section>
      </main>
    );
  }

  if (step === "consent") {
    return (
      <main className="patientJourney">
        <Progress active={1} />
        <section className="panel identityPanel">
          <span className="eyebrow">MyInfo demo consent</span>
          <h1>Share synthetic details?</h1>
          <p className="muted">ClinicPass will receive only this fictional profile for the demonstration.</p>
          <div className="consentList">
            <div><span>Full name</span><strong>Jamie Tan</strong></div>
            <div><span>Identity number</span><strong>••••123A</strong></div>
            <div><span>Email</span><strong>jamie.tan@example.test</strong></div>
          </div>
          <button className="button primary wide" type="button" onClick={allowMyInfo}>Allow MyInfo demo data</button>
          <button className="textButton" type="button" onClick={useManualEntry}>Do not share · enter manually</button>
          <p className="privacyNote">No real Singpass or MyInfo service is contacted. Identity remains subject to in-person verification.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="patientJourney">
      <Progress active={3} />
      <section className="panel intakePanel">
        <div className="panelHeading">
          <div><span className="eyebrow">Steps 2–3 of 6 · Profile and visit</span><h1>Tell us about this visit</h1></div>
          {identitySource === "singpass_demo" && <span className="demoPill">MyInfo demo filled</span>}
        </div>
        <form onSubmit={submit} className="formGrid">
          <label className="full">Full name<input value={profile.name} onChange={(event) => setProfile({ ...profile, name: event.target.value })} required minLength={2} placeholder="Jamie Tan" /></label>
          <label className="full">Email<input value={profile.email} onChange={(event) => setProfile({ ...profile, email: event.target.value })} type="email" required placeholder="jamie@example.test" /></label>
          <label>Fictional identity number<input value={profile.identity_number} onChange={(event) => setProfile({ ...profile, identity_number: event.target.value.toUpperCase() })} required minLength={4} maxLength={80} placeholder="S000123A" /></label>
          <label>Date of birth<input value={profile.date_of_birth} onChange={(event) => setProfile({ ...profile, date_of_birth: event.target.value })} type="date" required /></label>
          <label>Phone<input value={profile.phone} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} required placeholder="81234567" /></label>
          <label className="full">Address<input value={profile.address} onChange={(event) => setProfile({ ...profile, address: event.target.value })} required placeholder="10 Synthetic Street" /></label>
          <label>Postal code<input value={profile.postal_code} onChange={(event) => setProfile({ ...profile, postal_code: event.target.value })} required /></label>
          <label>Ethnicity<input value={profile.ethnicity} onChange={(event) => setProfile({ ...profile, ethnicity: event.target.value })} required /></label>
          <label>Sex<select value={profile.sex} onChange={(event) => setProfile({ ...profile, sex: event.target.value })} required><option value="">Select</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other / self-described</option><option value="prefer_not_to_say">Prefer not to say</option></select></label>
          <fieldset><legend>Visit type</legend><div className="segmented"><button type="button" className={scheduled ? "selected" : ""} onClick={() => setScheduled(true)}>Scheduled</button><button type="button" className={!scheduled ? "selected" : ""} onClick={() => setScheduled(false)}>Walk-in</button></div></fieldset>
          {scheduled && <label className="full">Appointment date<input name="appointment_date" type="date" required /></label>}
          <label className="full">Reason for visit
            <select name="visit_reason" defaultValue="healthier_sg_periodic_checkup" required>
              <option value="gp_consultation">GP consultation</option>
              <option value="corporate_insurer_screening">Corporate or insurer health screening</option>
              <option value="occupational_health_screening">Occupational health screening</option>
              <option value="employer_insurer_medical_exam">Employer or insurer medical examination</option>
              <option value="healthier_sg_periodic_checkup">Healthier SG or periodic check-up</option>
              <option value="other_unsure">Other or not sure</option>
            </select>
          </label>
          <fieldset className="full"><legend>Requested services</legend><p className="muted">Select the canonical services the clinic should check against the synthetic package.</p><div className="choiceCards"><label><input type="checkbox" name="requested_services" value="BASIC_SCREEN" defaultChecked /> Basic screening</label><label><input type="checkbox" name="requested_services" value="CBC" /> Full blood count</label><label><input type="checkbox" name="requested_services" value="CHEST_XRAY" /> Chest X-ray</label></div></fieldset>
          <fieldset className="full documentQuestion">
            <legend>Do you need to submit any documents for this visit?</legend>
            <p>For example, an insurance medical chit, referral, e-card, or government check-up letter.</p>
            <div className="choiceCards">
              {([ ["yes", "Yes", "I have relevant documents"], ["no", "No", "None were requested"], ["unsure", "Not sure", "Let the clinic confirm"] ] as const).map(([value, title, detail]) => (
                <button className={documentRequirement === value ? "selected" : ""} type="button" onClick={() => setDocumentRequirement(value)} key={value}><strong>{title}</strong><small>{detail}</small></button>
              ))}
            </div>
          </fieldset>
          {error && <div className="alert error full" role="alert">{error}</div>}
          <button className="button primary full" disabled={busy}>{busy ? "Saving…" : "Continue to documents"}</button>
        </form>
        <button className="textButton" type="button" onClick={() => setStep("choice")}>Change sign-in method</button>
      </section>
    </main>
  );
}
