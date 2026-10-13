// Static AST extraction only: never import or execute a downloaded website module.
const fs = require('node:fs');
const path = require('node:path');
const acorn = require('../artifacts/wiki-tools/node_modules/acorn');
const root = path.resolve(__dirname, '../artifacts/wiki');
let summonMode=false, sourceCards={};
function literal(n) {
  if (!n) throw Error('dynamic');
  if (n.type === 'Literal') return n.value;
  if (n.type === 'TemplateLiteral' && !n.expressions.length) return n.quasis[0].value.cooked;
  if (n.type === 'UnaryExpression' && n.operator === '!') return !literal(n.argument);
  if (n.type === 'UnaryExpression' && n.operator === '-') return -literal(n.argument);
  if (n.type === 'ArrayExpression') return n.elements.map(literal);
  if (n.type === 'ObjectExpression') return Object.fromEntries(n.properties.map(p => {
    if (p.type !== 'Property' || p.computed || p.method) throw Error('dynamic');
    return [p.key.name ?? p.key.value, literal(p.value)];
  }));
  // Explicit data-constructor schemas observed in the summon module; no JS execution.
  if (summonMode && n.type==='MemberExpression' && n.object.name==='o' && sourceCards[n.property.name]) return sourceCards[n.property.name];
  if (summonMode && n.type==='CallExpression' && n.callee.type==='Identifier') {
    const a=n.arguments.map(literal);
    if (n.callee.name==='c') return 'https://assets.wanxiangqiwiki.com/assets/summons/'+a[0];
    if (n.callee.name==='d') return {entityType:a[0],id:a[1],name:a[2],descriptionPlain:a[3]};
    if (n.callee.name==='f') return {name:a[0],original:a[1],enhancements:a[2]||[]};
    if (n.callee.name==='l') return {id:'summon-'+a[0],name:a[1],...(a[2]||{})};
  }
  if (n.type === 'CallExpression' && n.callee.type === 'MemberExpression') {
    const c=n.callee;
    if (c.object.name === 'JSON' && c.property.name === 'parse') return JSON.parse(literal(n.arguments[0]));
    if (c.object.name === 'Object' && c.property.name === 'freeze') return literal(n.arguments[0]);
  }
  throw Error('dynamic');
}
const outputs=[];
for (const file of fs.readdirSync(root).filter(f=>f.endsWith('.js') && !f.startsWith('pyodide'))) {
  const source=fs.readFileSync(path.join(root,file),'utf8');
  const ast=acorn.parse(source,{ecmaVersion:'latest',sourceType:'module'});
  summonMode=file.startsWith('summon-cards-'); sourceCards={};
  if (summonMode) for(const n of ast.body) if(n.type==='VariableDeclaration') for(const d of n.declarations) if(d.id.name==='o') sourceCards=literal(d.init);
  const datasets=[], texts=[];
  function visit(n) {
    if (!n || typeof n !== 'object') return;
    if (['ArrayExpression','ObjectExpression','CallExpression'].includes(n.type)) {
      try {
        const value=literal(n);
        if (value && typeof value==='object' && /[\u4e00-\u9fff]/.test(JSON.stringify(value))) {
          datasets.push({offset:n.start,value}); return;
        }
      } catch {}
    }
    if (n.type==='TemplateLiteral' || n.type==='Literal') {
      try { const value=literal(n); if (typeof value==='string' && /[\u4e00-\u9fff]/.test(value)) texts.push({offset:n.start,value}); } catch {}
    }
    for (const [k,v] of Object.entries(n)) {
      if (k==='start'||k==='end') continue;
      if (Array.isArray(v)) v.forEach(visit); else if (v && typeof v==='object') visit(v);
    }
  }
  visit(ast);
  outputs.push({file,datasets,texts});
  console.log(file, 'datasets',datasets.length,'texts',texts.length);
}
fs.writeFileSync(path.join(root,'embedded.json'),JSON.stringify(outputs,null,2)+'\n');
