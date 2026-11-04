import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Privacy Policy | Saath",
};

const REPO = "https://github.com/PrathameshTawar/meta-hackthon-top-2000-all-over-the-world";

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="4 November 2026">
      <p>
        Saath helps a family keep track of an ageing parent&apos;s bills, pensions, medicines and
        other obligations. This page explains what information Saath collects, why, and who can
        see it.
      </p>
      <p>
        Saath is currently a hackathon prototype. Please do not use it to store information you
        are not comfortable sharing with the people running the deployment you are using.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li>
          <strong>Family member details:</strong> name, role in the household (parent or child),
          WhatsApp phone number or Telegram ID, preferred language, time zone and quiet hours.
        </li>
        <li>
          <strong>Messages you send to the bot:</strong> voice notes, photos of bills and letters,
          documents and text. We store the transcribed or extracted text and a reference to the
          original media on WhatsApp or Telegram.
        </li>
        <li>
          <strong>Tasks created from those messages:</strong> payee, amount, due date, category,
          who claimed it, its status, and the exact quote from the message that each field came
          from.
        </li>
        <li>
          <strong>Health information, if your family uses the health features:</strong> medicine
          schedules, whether each dose was taken, and readings such as blood pressure, pulse or
          sugar levels, along with the alert thresholds your family sets.
        </li>
        <li>
          <strong>Activity history:</strong> a log of actions such as task claims, completions and
          reminders, kept so the family can see what happened and when.
        </li>
      </ul>

      <h2>How we use it</h2>
      <ul>
        <li>To turn messages into tasks and show them on your family&apos;s board.</li>
        <li>To send reminders and escalate unclaimed tasks or missed doses to other family members.</li>
        <li>To tell the parent when a task they sent has been completed.</li>
        <li>To detect and warn about likely scam messages (for example, requests for an OTP).</li>
      </ul>
      <p>We do not sell your information or use it for advertising.</p>

      <h2>Who can see it</h2>
      <ul>
        <li>Members of your household can see your household&apos;s tasks, evidence and health records.</li>
        <li>
          Message content is sent to Meta&apos;s AI model API to transcribe voice notes and read
          documents. Messages also pass through WhatsApp (Meta) or Telegram, under their own
          privacy policies.
        </li>
        <li>The operator of the Saath deployment you are using can access the database.</li>
      </ul>

      <h2>Medical information</h2>
      <p>
        Saath records medicine and vitals information so your family can stay informed. It does
        not interpret lab reports or give medical advice. Always consult a doctor about health
        decisions.
      </p>

      <h2>How long we keep it</h2>
      <p>
        Information is kept for as long as your household uses Saath. You can ask for your
        household&apos;s data to be deleted at any time (see below).
      </p>

      <h2>Your choices</h2>
      <ul>
        <li>Ask to see, correct or delete the information Saath holds about you.</li>
        <li>Stop messaging the bot at any time. Saath only processes messages you send it.</li>
      </ul>

      <h2>Contact</h2>
      <p>
        For privacy questions or deletion requests, open an issue on the{" "}
        <a href={`${REPO}/issues`}>project repository</a>.
      </p>
    </LegalPage>
  );
}
