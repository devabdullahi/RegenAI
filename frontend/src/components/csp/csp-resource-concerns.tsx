import { cn } from "@/lib/utils";
import type { CSPResourceConcernResult } from "@/lib/api/types";

/**
 * The densest block in the app: eight conservation areas read at a glance, the
 * way the scored rows are printed on a conservation plan sheet. One table,
 * hairline dividers, figures right-aligned in mono.
 */

interface CSPResourceConcernsProps {
  resourceConcerns: CSPResourceConcernResult[];
}

const COL_HEAD =
  "py-1.5 font-mono text-[0.6875rem] font-medium tracking-[0.14em] text-muted-foreground uppercase";

export function CSPResourceConcerns({
  resourceConcerns,
}: CSPResourceConcernsProps) {
  const metCount = resourceConcerns.filter((rc) => rc.currently_met).length;
  const total = resourceConcerns.length;

  if (total === 0) {
    return (
      <section aria-labelledby="resource-concerns-heading" className="space-y-2">
        <div className="rule-head">
          <h2 id="resource-concerns-heading">Conservation areas</h2>
          <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        </div>
        <p className="text-sm text-muted-foreground">
          No conservation area results yet. Run an eligibility evaluation to see
          them.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="resource-concerns-heading" className="space-y-2">
      <div className="rule-head">
        <h2 id="resource-concerns-heading">Conservation areas</h2>
        <span aria-hidden="true" className="h-px flex-1 bg-rule" />
        <span className="font-mono text-[0.6875rem] text-foreground">
          {metCount} / {total} met
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[20rem] text-sm">
          <caption className="sr-only">
            {metCount} of {total} conservation areas are above the stewardship
            threshold
          </caption>
          <thead>
            <tr className="border-b border-rule">
              <th scope="col" className={cn(COL_HEAD, "text-left")}>
                Area
              </th>
              <th scope="col" className={cn(COL_HEAD, "pl-3 text-right")}>
                Score
              </th>
              <th scope="col" className={cn(COL_HEAD, "pl-3 text-right")}>
                Points
              </th>
              <th scope="col" className={cn(COL_HEAD, "pl-3 text-right")}>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {resourceConcerns.map((rc) => (
              <tr key={rc.code} className="border-b border-rule last:border-0">
                <th
                  scope="row"
                  className="py-2 pr-3 text-left align-top font-normal"
                >
                  <span className="block text-sm text-foreground">
                    {rc.name}
                  </span>
                  {rc.evidence.length > 0 && (
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {rc.evidence.slice(0, 2).join(" · ")}
                    </span>
                  )}
                </th>
                <td className="py-2 pl-3 text-right align-top font-mono text-sm whitespace-nowrap text-foreground">
                  {rc.score} / 100
                </td>
                <td className="py-2 pl-3 text-right align-top font-mono text-sm whitespace-nowrap text-foreground">
                  {rc.points_earned} pts
                </td>
                <td
                  className={cn(
                    "py-2 pl-3 text-right align-top font-mono text-[0.6875rem] tracking-[0.08em] whitespace-nowrap uppercase",
                    rc.currently_met ? "text-success" : "text-muted-foreground"
                  )}
                >
                  {rc.currently_met ? "Met" : "Not met"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground">
        Met means the area is above the stewardship threshold and earning points.
        Not met means there are recommendations to work through.
      </p>
    </section>
  );
}
