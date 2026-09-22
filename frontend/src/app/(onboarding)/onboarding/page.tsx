import { ButtonLink } from "@/components/shared/button-link";
import { RuleHead } from "@/components/shared/record";

/**
 * The steps are a real sequence, so they are numbered. Each line says what we
 * ask for and why it is needed — no feature cards.
 */
const SETUP_STEPS = [
  {
    number: 1,
    title: "Farm info",
    detail:
      "Name, state, county and total acres. The county code is what we use to pull your soil survey and weather.",
  },
  {
    number: 2,
    title: "Fields",
    detail: "Each field with its acres and crop, so advice is per field.",
  },
  {
    number: 3,
    title: "Practices",
    detail:
      "What you already do — cover crop, no-till, rotation. This is what earns program points.",
  },
  {
    number: 4,
    title: "Goals",
    detail: "What you want most: cost-share money, soil health, or yield.",
  },
  {
    number: 5,
    title: "Confirm",
    detail: "Check it over. We then pull soil and weather and write your first recommendations.",
  },
];

export default function OnboardingWelcome() {
  return (
    <div className="flex flex-col gap-8">
      <div className="border-b-2 border-rule-strong pb-4">
        <h1 className="font-heading text-3xl font-bold">Set up your farm</h1>
        <p className="reading mt-2 text-muted-foreground">
          Five short steps, about five minutes. Everything you enter stays your
          record — you can change any of it later.
        </p>
      </div>

      <section className="flex flex-col gap-4">
        <RuleHead label="What we will ask" />
        <ol className="flex flex-col">
          {SETUP_STEPS.map((step) => (
            <li
              key={step.number}
              className="flex gap-4 border-b border-border py-3 last:border-b-0"
            >
              <span className="font-mono text-sm text-muted-foreground tabular-nums">
                {String(step.number).padStart(2, "0")}
              </span>
              <div>
                <p className="font-heading text-base font-semibold">
                  {step.title}
                </p>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {step.detail}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <ButtonLink href="/onboarding/farm" size="lg" className="self-start">
        Start with farm info
      </ButtonLink>
    </div>
  );
}
