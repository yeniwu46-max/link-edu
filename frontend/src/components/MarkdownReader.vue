<script setup>
import { computed } from "vue";

const props = defineProps({
  content: { type: String, default: "" },
});

function inlineParts(text) {
  const normalized = text.replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '$1/$2').replace(/\\[()]/g, '');
  const pattern = /\[([^\]]+)]\((https?:\/\/[^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g;
  const parts = [];
  let cursor = 0;
  let match;

  while ((match = pattern.exec(normalized))) {
    if (match.index > cursor) {
      parts.push({ type: "text", text: normalized.slice(cursor, match.index) });
    }
    parts.push(match[1] ? { type: "link", text: match[1], href: match[2] }
      : { type: match[3] ? 'strong' : 'code', text: match[3] || match[4] });
    cursor = match.index + match[0].length;
  }

  if (cursor < normalized.length) {
    parts.push({ type: "text", text: normalized.slice(cursor) });
  }
  return parts;
}

const blocks = computed(() => {
  const result = [];
  let list = null;
  let currentTable = null;
  const closeList = () => {
    list = null;
  };

  for (const raw of props.content.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) {
      closeList();
      currentTable = null;
      continue;
    }

    if (line.startsWith('|') && line.endsWith('|')) {
      closeList();
      const cells = line.slice(1, -1).split('|').map(cell => cell.trim());
      if (cells.every(cell => /^:?-{3,}:?$/.test(cell))) continue;
      if (!currentTable) {
        currentTable = { type: 'table', rows: [] };
        result.push(currentTable);
      }
      currentTable.rows.push(cells.map(inlineParts));
      continue;
    }
    currentTable = null;

    const heading = line.match(/^(#{1,3})\s+(.+)/);
    if (heading) {
      closeList();
      result.push({
        type: "heading",
        level: heading[1].length,
        parts: inlineParts(heading[2]),
      });
      continue;
    }

    const quote = line.match(/^>\s?(.+)/);
    if (quote) {
      closeList();
      result.push({ type: "quote", parts: inlineParts(quote[1]) });
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.+)/);
    const bullet = line.match(/^[-*]\s+(.+)/);
    if (ordered || bullet) {
      const kind = ordered ? "ordered" : "unordered";
      if (!list || list.kind !== kind) {
        list = { type: "list", kind, items: [] };
        result.push(list);
      }
      list.items.push(inlineParts((ordered || bullet)[1]));
      continue;
    }

    closeList();
    result.push({ type: "paragraph", parts: inlineParts(line) });
  }

  return result;
});
</script>

<template>
  <article class="markdown-reader">
    <template v-for="(block, index) in blocks" :key="index">
      <component :is="`h${block.level}`" v-if="block.type === 'heading'">
        <template v-for="(part, partIndex) in block.parts" :key="partIndex">
          <a
            v-if="part.type === 'link'"
            :href="part.href"
            target="_blank"
            rel="noopener noreferrer"
          >{{ part.text }}</a>
          <component :is="part.type === 'strong' ? 'strong' : part.type === 'code' ? 'code' : 'span'" v-else>{{ part.text }}</component>
        </template>
      </component>

      <blockquote v-else-if="block.type === 'quote'">
        <template v-for="(part, partIndex) in block.parts" :key="partIndex">
          <a
            v-if="part.type === 'link'"
            :href="part.href"
            target="_blank"
            rel="noopener noreferrer"
          >{{ part.text }}</a>
          <component :is="part.type === 'strong' ? 'strong' : part.type === 'code' ? 'code' : 'span'" v-else>{{ part.text }}</component>
        </template>
      </blockquote>

      <component
        :is="block.kind === 'ordered' ? 'ol' : 'ul'"
        v-else-if="block.type === 'list'"
      >
        <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
          <template v-for="(part, partIndex) in item" :key="partIndex">
            <a
              v-if="part.type === 'link'"
              :href="part.href"
              target="_blank"
              rel="noopener noreferrer"
            >{{ part.text }}</a>
            <component :is="part.type === 'strong' ? 'strong' : part.type === 'code' ? 'code' : 'span'" v-else>{{ part.text }}</component>
          </template>
        </li>
      </component>

      <div v-else-if="block.type === 'table'" class="reader-table-scroll">
        <table><tbody>
          <tr v-for="(row, rowIndex) in block.rows" :key="rowIndex">
            <component :is="rowIndex === 0 ? 'th' : 'td'" v-for="(cell, cellIndex) in row" :key="cellIndex">
              <template v-for="(part, partIndex) in cell" :key="partIndex">
                <a v-if="part.type === 'link'" :href="part.href" target="_blank" rel="noopener noreferrer">{{ part.text }}</a>
                <component :is="part.type === 'strong' ? 'strong' : part.type === 'code' ? 'code' : 'span'" v-else>{{ part.text }}</component>
              </template>
            </component>
          </tr>
        </tbody></table>
      </div>
      <p v-else>
        <template v-for="(part, partIndex) in block.parts" :key="partIndex">
          <a
            v-if="part.type === 'link'"
            :href="part.href"
            target="_blank"
            rel="noopener noreferrer"
          >{{ part.text }}</a>
          <component :is="part.type === 'strong' ? 'strong' : part.type === 'code' ? 'code' : 'span'" v-else>{{ part.text }}</component>
        </template>
      </p>
    </template>
  </article>
</template>

<style scoped>
.markdown-reader {
  max-width: 760px;
  margin: 0 auto;
  padding: 34px clamp(20px, 5vw, 64px) 64px;
  color: #ded8e2;
  line-height: 1.85;
}

.markdown-reader :deep(h1) {
  margin: 0 0 24px;
  color: #fff;
  font-size: clamp(26px, 4vw, 38px);
  line-height: 1.25;
}

.markdown-reader :deep(h2) {
  margin: 42px 0 14px;
  color: #f4eef7;
  font-size: 21px;
  line-height: 1.4;
}

.markdown-reader :deep(h3) {
  margin: 28px 0 10px;
  color: #ffb67f;
  font-size: 15px;
  letter-spacing: 0.04em;
}

.markdown-reader p,
.markdown-reader li,
.markdown-reader blockquote {
  font-size: 14px;
}

.markdown-reader p {
  margin: 10px 0;
}

.markdown-reader ul,
.markdown-reader ol {
  display: grid;
  gap: 9px;
  margin: 12px 0;
  padding-left: 22px;
}

.markdown-reader blockquote {
  margin: 20px 0 30px;
  padding: 14px 18px;
  border-left: 2px solid #ff7a18;
  background: rgba(255, 122, 24, 0.08);
  color: #cfc5d4;
}

.markdown-reader a {
  color: #ffad70;
  text-decoration-color: rgba(255, 173, 112, 0.45);
  text-underline-offset: 3px;
}

.markdown-reader a:hover {
  color: #ffd0ad;
}
.reader-table-scroll { overflow-x: auto; margin: 18px 0; }
.markdown-reader table { border-collapse: collapse; width: 100%; font-size: 14px; }
.markdown-reader th, .markdown-reader td { border: 1px solid #514657; padding: 10px 12px; text-align: left; }
.markdown-reader th { background: #2b2331; color: #fff; }
.markdown-reader code { padding: 2px 4px; background: #2b2331; }
</style>
