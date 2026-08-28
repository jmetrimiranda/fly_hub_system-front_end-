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
      // As duas regras base do `js.configs.recommended` não valem para TS: o
      // compilador já acusa identificador inexistente (e o ESLint não conhece
      // os globais do DOM), e a versão base de no-unused-vars não entende
      // assinatura de tipo — daria falso positivo em toda interface de store.
      "no-undef": "off",
      "no-unused-vars": "off",
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
  {
    // Mesma ideia da regra do axios, um nível acima: nem chamada de rede nem
    // endereço de rede fora de src/services/api. Um `src="/api/v1/…"` num
    // componente é resolvido contra a origem da página — o Vite na 5173 em
    // desenvolvimento —, que responde index.html; a imagem some sem erro e sem
    // requisição nenhuma no Network. Quem precisa do endereço chama `apiUrl`.
    files: ["src/components/**/*.{ts,tsx}", "src/pages/**/*.{ts,tsx}", "src/hooks/**/*.ts"],
    ignores: ["**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/^\\/api\\//]",
          message:
            "Endereço de API não se monta em componente. Use apiUrl() ou um método de @/services/api.",
        },
        {
          selector: "TemplateElement[value.raw=/^\\/api\\//]",
          message:
            "Endereço de API não se monta em componente. Use apiUrl() ou um método de @/services/api.",
        },
      ],
    },
  },
  { ignores: ["dist", "src/services/api/client.ts", "src/types/api.generated.ts"] },
];
