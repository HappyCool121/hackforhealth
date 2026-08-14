import { connection } from "next/server";
import ClinicLoginForm, { DemoCredentials } from "./ClinicLoginForm";

function enabled(value: string | undefined, fallback: boolean) {
  if (value === undefined) return fallback;
  return !["0", "false", "no", "off"].includes(value.toLowerCase());
}

export default async function ClinicLogin() {
  await connection();
  const showDemoCredentials = enabled(process.env.SHOW_DEMO_CREDENTIALS, true);
  const assistantPassword = process.env.STAFF_ASSISTANT_PASSWORD;
  const managerPassword = process.env.STAFF_MANAGER_PASSWORD;
  const demoCredentials: DemoCredentials | undefined = showDemoCredentials && assistantPassword && managerPassword ? {
    assistantEmail: process.env.STAFF_ASSISTANT_EMAIL || "assistant@clinicpass.test",
    assistantPassword,
    managerEmail: process.env.STAFF_MANAGER_EMAIL || "manager@clinicpass.test",
    managerPassword,
  } : undefined;
  return <ClinicLoginForm demoCredentials={demoCredentials} />;
}
