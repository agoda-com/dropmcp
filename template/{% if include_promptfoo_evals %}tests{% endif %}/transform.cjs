const fs = require("fs");
const path = require("path");

/** Promptfoo renders vars with Nunjucks; JSX `{{` / `}}` in skill markdown must not parse as templates. */
function escapeNunjucksDoubleBraces(content) {
  return content
    .replace(/\{\{/g, "{\u200B{")
    .replace(/\}\}/g, "}\u200B}");
}

module.exports = function (vars) {
  if (vars.skill_path) {
    vars.skill_content = escapeNunjucksDoubleBraces(
      fs.readFileSync(path.resolve(__dirname, "..", vars.skill_path), "utf-8"),
    );
  }
  return vars;
};
