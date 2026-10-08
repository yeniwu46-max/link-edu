import { readFile,writeFile } from 'node:fs/promises'
const source=await readFile(new URL('../backend/data/assistant-guide.json',import.meta.url),'utf8')
JSON.parse(source.replace(/^\uFEFF/,''))
await writeFile(new URL('../frontend/src/data/systemGuide.json',import.meta.url),source.replace(/^\uFEFF/,''))
