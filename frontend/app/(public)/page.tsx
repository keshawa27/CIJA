import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Ask for support</h1>
      <p className="text-lg text-slate-700">
        Tell us a little about your situation and how we can safely contact you. A member of our team will get in
        touch.
      </p>
      <ul className="list-disc space-y-1 pl-5 text-slate-700">
        <li>The form takes about five minutes.</li>
        <li>We only ask for what we need to help you.</li>
        <li>
          You can leave this site at any time with the <strong>Quick exit</strong> button.
        </li>
      </ul>
      <p className="error">
        If you are in immediate danger, call <strong>000</strong>.
      </p>
      <div className="flex flex-wrap gap-3">
        <Link href="/intake" className="btn">
          Start the form
        </Link>
        <Link href="/status" className="btn-secondary">
          Check a request
        </Link>
      </div>
    </div>
  );
}
