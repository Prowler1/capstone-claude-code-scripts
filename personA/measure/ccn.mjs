// McCabe cyclomatic complexity per function for TS/TSX, via the TypeScript compiler API.
// CCN = 1 + if, ?:, case, for/for-in/for-of/while/do, catch, &&, ||, ?? (and &&=, ||=, ??=).
// Decision points inside a nested function count toward that nested function only.
// Usage: node ccn.mjs <root> [<root>...]  -> CSV: file,function,startLine,endLine,lines,ccn
import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'

const K = ts.SyntaxKind
const isFn = n => ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n) ||
  ts.isMethodDeclaration(n) || ts.isGetAccessor(n) || ts.isSetAccessor(n) || ts.isConstructorDeclaration(n)
const LOGIC = new Set([K.AmpersandAmpersandToken, K.BarBarToken, K.QuestionQuestionToken,
  K.AmpersandAmpersandEqualsToken, K.BarBarEqualsToken, K.QuestionQuestionEqualsToken])
const isDecision = n => ts.isIfStatement(n) || ts.isConditionalExpression(n) || ts.isCaseClause(n) ||
  ts.isForStatement(n) || ts.isForInStatement(n) || ts.isForOfStatement(n) || ts.isWhileStatement(n) ||
  ts.isDoStatement(n) || ts.isCatchClause(n) || (ts.isBinaryExpression(n) && LOGIC.has(n.operatorToken.kind))

function nameOf(n) {
  if (n.name && ts.isIdentifier(n.name)) return n.name.text
  const p = n.parent
  if (p && ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text
  if (p && ts.isPropertyAssignment(p) && ts.isIdentifier(p.name)) return p.name.text
  return '(anonymous)'
}

const files = []
const walkDir = d => { for (const e of fs.readdirSync(d, { withFileTypes: true })) {
  const p = path.join(d, e.name)
  if (e.isDirectory()) { if (e.name !== 'node_modules' && e.name !== 'types') walkDir(p) }
  else if (/\.tsx?$/.test(e.name) && !e.name.endsWith('.d.ts')) files.push(p) } }
process.argv.slice(2).forEach(r => fs.statSync(r).isDirectory() ? walkDir(r) : files.push(r))

console.log('file,function,start,end,lines,ccn')
for (const f of files) {
  const src = ts.createSourceFile(f, fs.readFileSync(f, 'utf8'), ts.ScriptTarget.Latest, true,
    f.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const line = pos => src.getLineAndCharacterOfPosition(pos).line + 1
  const visit = (n, fnStack) => {
    if (isFn(n)) {
      const rec = { n, ccn: 1 }; fnStack = [...fnStack, rec]
      ts.forEachChild(n, c => visit(c, fnStack))
      const s = line(n.getStart(src)), e = line(n.end)
      console.log([f.split(String.fromCharCode(92)).join('/'), nameOf(n), s, e, e - s + 1, rec.ccn].join(','))
      return
    }
    if (isDecision(n) && fnStack.length) fnStack.at(-1).ccn++
    ts.forEachChild(n, c => visit(c, fnStack))
  }
  visit(src, [])
}
