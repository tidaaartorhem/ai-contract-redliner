import { useMemo, useState } from "react";
import type { RedlineDeskData, Route } from "../types";
import { ContractCard } from "./shared";

type RouteFilter = "all" | Route;

const ROUTES: Route[] = ["APPROVE", "SEND_TO_LEGAL", "ESCALATE"];

/** The review queue: every contract, its route, and the redline draft behind a human gate. */
export default function QueueView({ data }: { data: RedlineDeskData }) {
  const [route, setRoute] = useState<RouteFilter>("all");
  const [rule, setRule] = useState<string>("all");
  const [query, setQuery] = useState("");

  const rules = useMemo(() => data.playbook.rules.map((r) => r.id).sort(), [data]);

  const shown = data.contracts.filter(
    (c) =>
      (route === "all" || c.route === route) &&
      (rule === "all" ||
        c.clauses.some((cl) => cl.rule_id === rule && cl.tier !== "ACCEPT")) &&
      (query.trim() === "" ||
        (c.title + " " + (c.document_name ?? "") + " " + (c.parties ?? "") + " " + c.contract_id)
          .toLowerCase()
          .includes(query.trim().toLowerCase())),
  );

  return (
    <div>
      <div className="card">
        <h2>Review queue</h2>
        <p className="muted">
          {shown.length} of {data.contracts.length} contracts shown. APPROVE means every playbook
          rule passed; SEND_TO_LEGAL means at least one clause needs a redline; ESCALATE means a
          REJECT-tier clause (or an 80+ risk score) — do not sign. Every redline draft needs human
          approval — nothing is final until a person signs off.
        </p>
        <div className="filters">
          <div className="seg">
            {(["all", ...ROUTES] as const).map((f) => (
              <button key={f} className={route === f ? "active" : ""} onClick={() => setRoute(f)}>
                {f === "all"
                  ? `All (${data.contracts.length})`
                  : `${f.replace("_", " ")} (${data.contracts.filter((t) => t.route === f).length})`}
              </button>
            ))}
          </div>
          <div className="filter-row">
            <select value={rule} onChange={(e) => setRule(e.target.value)} aria-label="Rule filter">
              <option value="all">All rules</option>
              {rules.map((r) => (
                <option key={r} value={r}>
                  {data.playbook.categories[r] ?? r}
                </option>
              ))}
            </select>
            <input
              type="search"
              placeholder="Search contracts…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
      </div>
      {shown.map((c) => (
        <ContractCard key={c.contract_id} c={c} />
      ))}
    </div>
  );
}
