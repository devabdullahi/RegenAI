import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // server-client.ts reads cookies() and imports "server-only"; it breaks in
  // Client Components. Components and the all-client onboarding flow must use
  // @/lib/api/client. (Client pages elsewhere in src/app are not detectable
  // by path, so review "use client" pages by hand.)
  {
    files: [
      "src/components/**/*.{ts,tsx}",
      "src/app/(onboarding)/**/*.{ts,tsx}",
      "src/app/**/error.tsx",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/lib/api/server-client", "**/lib/api/server-client"],
              message:
                "server-client is for Server Components only. Import api from @/lib/api/client instead.",
            },
          ],
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
