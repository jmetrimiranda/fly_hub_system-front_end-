import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsparser,
      parserOptions: { ecmaFeatures: { jsx: true }, project: "./tsconfig.json" },
    },
    plugins: { "@typescript-eslint": tseslint, "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      // Regra do projeto: nada de fetch/axios fora de src/services/api.
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["axios"],
              message: "Use os services em @/services/api em vez de chamar axios direto.",
            },
          ],
        },
      ],
    },
  },
  { ignores: ["dist", "src/services/api/client.ts", "src/types/api.generated.ts"] },
];
