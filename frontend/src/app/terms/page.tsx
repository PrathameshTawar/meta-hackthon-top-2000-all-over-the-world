import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Terms of Use | Saath",
};

const REPO = "https://github.com/PrathameshTawar/meta-hackthon-top-2000-all-over-the-world";

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Use" updated="4 November 2026">
      <p>
        By using Saath, through the web board, WhatsApp or Telegram, you agree to these terms.
        If you do not agree, please do not use it.
      </p>

      <h2>What Saath is</h2>
      <p>
        Saath is a prototype built for a hackathon. It reads messages from a family member and
        turns them into a shared list of tasks and reminders. It is provided free of charge and
        may change, break or be shut down without notice.
      </p>

      <h2>Check before you pay</h2>
      <p>
        Saath extracts amounts, due dates and payees automatically, and it can make mistakes.
        Every task shows the original quote it was taken from. Always check the original bill or
        letter before making a payment or acting on a deadline. Saath does not make payments on
        your behalf.
      </p>

      <h2>Not medical advice</h2>
      <p>
        Medicine reminders and vitals alerts help families stay informed. They are not a
        substitute for a doctor, and Saath does not diagnose conditions or interpret test
        results. In an emergency, contact local emergency services.
      </p>

      <h2>Your responsibilities</h2>
      <ul>
        <li>Only add family members who have agreed to be part of your household on Saath.</li>
        <li>Do not use Saath to send spam, harass anyone, or share content you have no right to share.</li>
        <li>Keep the admin secret for your deployment private.</li>
      </ul>

      <h2>Third-party services</h2>
      <p>
        Saath relies on WhatsApp, Telegram and Meta&apos;s AI model API. Your use of those services
        is also governed by their own terms.
      </p>

      <h2>No warranty</h2>
      <p>
        Saath is provided &quot;as is&quot;, without warranties of any kind. To the extent the law
        allows, the authors are not liable for missed payments, late fees, missed doses or any
        other loss arising from use of Saath.
      </p>

      <h2>Privacy</h2>
      <p>
        How we handle your information is described in the <Link href="/privacy">Privacy Policy</Link>.
      </p>

      <h2>Changes and contact</h2>
      <p>
        We may update these terms; the date at the top shows the latest version. Questions can be
        raised on the <a href={`${REPO}/issues`}>project repository</a>.
      </p>
    </LegalPage>
  );
}
