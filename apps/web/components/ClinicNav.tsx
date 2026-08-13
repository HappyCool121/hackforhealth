"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function ClinicNav({ role }: { role?: string }) {
  const path = usePathname(); const router = useRouter();
  return <aside className="clinicNav"><Link className="brand inverse" href="/clinic/queue"><span className="brandMark">C</span> ClinicPass</Link><nav><Link className={path.includes("queue") ? "active" : ""} href="/clinic/queue">Review queue</Link>{role === "manager" && <Link className={path.includes("admin") ? "active" : ""} href="/clinic/admin">Manager view</Link>}</nav><button onClick={async () => { await api("/auth/logout", { method: "POST" }); router.push("/clinic"); }}>Sign out</button></aside>;
}

