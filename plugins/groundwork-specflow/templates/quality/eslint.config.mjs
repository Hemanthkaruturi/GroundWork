// GroundWork standard JS/TS lint rules (STANDARD.md §5i). Change a rule only on purpose, with a reason.
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";

export default tseslint.config(
  { ignores: ["dist/", "build/", "coverage/", "node_modules/", ".next/"] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  prettier,
  {
    rules: {
      eqeqeq: "error",
      "no-empty": "error",                                   // no swallowed errors: catch (e) {}
      "no-console": ["warn", { allow: ["warn", "error"] }],  // use the project's logger
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/ban-ts-comment": ["error", { "ts-expect-error": "allow-with-description" }],
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
);
