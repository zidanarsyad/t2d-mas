import { Trophy } from "lucide-react";
import { formatNumber } from "../lib/format.js";
import { shortAgentName } from "../lib/workflow.js";
import Term from "./Term";

/** Contract Net bids: skill, workload, cost and the utility that decides the winner. */
export default function BidTable({ bids, winner }) {
  if (!bids?.length) return null;
  const ordered = [...bids].sort((a, b) => Number(b.utility) - Number(a.utility));
  return (
    <div className="table-wrap">
      <table className="table">
        <caption>
          <Term id="utility">Utility</Term> = 0.5 × skill + 0.3 × (1 − workload) + 0.2 × (1 − cost). The highest utility wins.
        </caption>
        <thead>
          <tr>
            <th scope="col">Bidder</th>
            <th scope="col">Skill</th>
            <th scope="col">Workload</th>
            <th scope="col">Cost</th>
            <th scope="col">Utility</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((bid) => {
            const won = (bid.worker_id || bid.worker) === winner;
            return (
              <tr key={bid.worker_id || bid.worker} className={won ? "is-winner" : ""}>
                <th scope="row">
                  {won && <Trophy size={14} aria-hidden="true" />} {bid.squad ? `${bid.squad} squad` : shortAgentName(bid.worker_id || bid.worker)}
                  {won && <span className="tag tag-green winner-tag">Winner</span>}
                </th>
                <td>{formatNumber(Number(bid.skill) * 100)}%</td>
                <td>{formatNumber(Number(bid.load) * 100)}%</td>
                <td>{formatNumber(bid.cost, 2)}</td>
                <td>
                  <b>{formatNumber(bid.utility, 3)}</b>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
