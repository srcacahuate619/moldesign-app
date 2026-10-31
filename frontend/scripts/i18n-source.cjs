"use strict";
const ts = require("typescript");

// Candidatos de salida humana en módulos TS. No interpreta datos del backend.
function collectSource(source, file, rules) {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const rows = [];
  function scalarReachesOutput(name, text) {
    let output = false;
    function visit(n) {
      if (ts.isIdentifier(n) && n.text === name && !(ts.isVariableDeclaration(n.parent) && n.parent.name === n)) {
        let cursor = n;
        while (cursor.parent) {
          const parent = cursor.parent;
          if (ts.isCallExpression(parent) || ts.isNewExpression(parent)) {
            const callee = parent.expression.getText(sf);
            if (/^(console\.|logger\.)/.test(callee)) break;
            if (callee === "t" && rules.translated(text)) break;
            if (/^(t|Error|\w*Error|setError|setWarning|setMessage|alert|toast(?:\.\w+)?)$/.test(callee)) { output = true; break; }
          }
          if (ts.isReturnStatement(parent) || ts.isJsxExpression(parent)) { output = true; break; }
          if (ts.isStatement(parent)) break;
          cursor = parent;
        }
      }
      ts.forEachChild(n, visit);
    }
    visit(sf);
    return output;
  }
  function inspect(node, text) {
    text = text.replace(/\s+/g, " ").trim();
    if (!rules.spanish(text) || rules.technical(text)) return;
    if (/^[\w-]+$/.test(text) && /^[a-z]/.test(text)) return;
    if (/^[a-z][\w]*_/.test(text) && !/\s/.test(text.replace(/\$\{[^}]*\}/g, ""))) return;
    let cursor = node, scope = "", visible = false;
    while (cursor.parent) {
      const parent = cursor.parent;
      if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent) || ts.isLiteralTypeNode(parent)) return;
      if (ts.isPropertyAssignment(parent) && parent.name === cursor) return;
      if (ts.isPropertyAssignment(parent) && ["es", "en"].includes(parent.name.getText(sf).replace(/['"]/g, ""))
        && file.endsWith("LanguageContext.tsx")) return;
      if (ts.isBinaryExpression(parent) && [
        ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
        ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken,
      ].includes(parent.operatorToken.kind)) return;
      if (ts.isCaseClause(parent) && parent.expression === cursor) return;
      if (ts.isCallExpression(parent) || ts.isNewExpression(parent)) {
        const callee = parent.expression.getText(sf);
        if (/^(console\.|logger\.)/.test(callee)) return;
        if (callee === "t") {
          const argument = parent.arguments.findIndex(a => node.pos >= a.pos && node.end <= a.end);
          if (argument !== 0 || rules.translated(text)) return;
          visible = true; // t("frase") no es traducción si la frase no tiene alias exacto.
        }
        if (/^(Error|\w*Error|alert|confirm|setError|setWarning|setMessage|toast(?:\.\w+)?)$/.test(callee)) visible = true;
      }
      if (ts.isReturnStatement(parent)) visible = true;
      if (ts.isVariableDeclaration(parent) && ts.isIdentifier(parent.name)
        && (constant(parent.initializer) !== undefined || ts.isTemplateExpression(parent.initializer))
        && scalarReachesOutput(parent.name.text, text)) visible = true;
      if (ts.isPropertyAssignment(parent) && rules.properties.has(parent.name.getText(sf).replace(/['"]/g, ""))) visible = true;
      if (!scope && ts.isFunctionLike(parent)) scope = parent.name?.getText(sf) || parent.parent?.name?.getText(sf) || "(anónima)";
      cursor = parent;
    }
    if (!visible) return;
    rows.push({ file, line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1, text, scope });
  }
  function constant(node) {
    if (ts.isStringLiteralLike(node)) return node.text;
    if (ts.isParenthesizedExpression(node)) return constant(node.expression);
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
      const a = constant(node.left), b = constant(node.right);
      if (a !== undefined && b !== undefined) return a + b;
    }
  }
  function visit(node) {
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
      const text = constant(node);
      if (text !== undefined) { inspect(node, text); return; }
    }
    if (ts.isTemplateExpression(node)) {
      inspect(node, node.head.text + node.templateSpans.map(s => "${" + s.expression.getText(sf) + "}" + s.literal.text).join(""));
      for (const s of node.templateSpans) visit(s.expression);
      return;
    }
    if (ts.isStringLiteralLike(node)) inspect(node, node.text);
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return rows;
}


function translatedComparisons(source, file) {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const rows = [];
  function visit(node) {
    if (ts.isBinaryExpression(node) && [
      ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
      ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken,
    ].includes(node.operatorToken.kind) && /\bTRANSLATIONS\.es(?:\.|\[)|\bt\s*\(/.test(node.getText(sf))) {
      rows.push({ file, line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1,
        text: node.getText(sf), scope: "comparación con texto traducido" });
    }
    ts.forEachChild(node, visit);
  }
  visit(sf);
  return rows;
}

module.exports = { collectSource, translatedComparisons };
