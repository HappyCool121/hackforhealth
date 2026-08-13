import Link from "next/link";

export default function Home() {
  return (
    <main>
      <section className="hero">
        <div>
          <span className="eyebrow">Pre-registration, made clearer</span>
          <h1>Arrive ready.<br />Start care sooner.</h1>
          <p>ClinicPass helps patients prepare visit details and supporting documents before arrival, then gives clinic teams one evidence-backed review queue.</p>
          <div className="actions">
            <Link className="button primary" href="/patient/start">Start pre-registration</Link>
            <Link className="button secondary" href="/clinic">Open clinic workspace</Link>
          </div>
        </div>
        <div className="heroCard">
          <div className="step"><b>1</b><span><strong>Confirm synthetic details</strong><small>Simulated Singpass/MyInfo or manual entry</small></span></div>
          <div className="step"><b>2</b><span><strong>Photograph or upload documents</strong><small>AGNES reads PDFs, screenshots, and photos</small></span></div>
          <div className="step"><b>3</b><span><strong>Resolve issues early</strong><small>Clinic staff make the final administrative decision</small></span></div>
        </div>
      </section>
      <section className="trustGrid">
        <article><span>01</span><h2>Evidence, not guesswork</h2><p>Every extracted detail links back to readable page evidence.</p></article>
        <article><span>02</span><h2>Rules stay deterministic</h2><p>AI extracts; transparent rules calculate readiness.</p></article>
        <article><span>03</span><h2>People stay in control</h2><p>Clinic staff review exceptions and confirm originals on site.</p></article>
      </section>
    </main>
  );
}
