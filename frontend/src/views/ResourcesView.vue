<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import DraggableResourceCard from "../components/DraggableResourceCard.vue";
import MarkdownReader from "../components/MarkdownReader.vue";
import CourseResourceCatalog from "../components/CourseResourceCatalog.vue";
import SplitTitle from "../components/fx/SplitTitle.vue";
import { libraryResources, libraryTabs } from "../data/libraryResources";
import { boardCoverFor } from "../data/libraryBoardCovers";

const tab = ref("全部");
const collection = ref('library');
const activeCard = ref(libraryResources[0].id);
const selected = ref(null);
const markdown = ref("");
const loading = ref(false);
const loadError = ref("");
const layoutKey = ref(0);
const readerRef = ref(null);
let readerTrigger = null;
let requestId = 0;

const categoryTone = {
  官方标准: "official",
  课题专包: "topic",
  评课说明: "review",
  实操清单: "checklist",
  院校案例: "case",
  外部资源: "external",
};

const visible = computed(() => {
  if (tab.value === "全部") return libraryResources;
  const matches = libraryResources.filter((item) => item.category === tab.value);
  const slots = {
    1: [38],
    2: [22, 58],
    3: [7, 38, 69],
  }[matches.length] || [4, 27, 50, 73];

  return matches.map((item, index) => ({
    ...item,
    position: {
      ...item.position,
      left: slots[index],
      top: index % 2 === 0 ? 70 : 130,
      rotate: index % 2 === 0 ? -2 : 3,
    },
  }));
});

const boardColumns = computed(() => {
  const order = libraryTabs.filter((name) => name !== "全部");
  const items = visible.value;
  return order
    .map((category) => ({
      category,
      tone: categoryTone[category] || "topic",
      items: items.filter((item) => item.category === category),
    }))
    .filter((column) => column.items.length);
});

/** Fill left-to-right so shorter categories do not leave empty holes between columns. */
const boardCards = computed(() =>
  boardColumns.value.flatMap((column) =>
    column.items.map((item) => ({
      ...item,
      tone: column.tone,
    })),
  ),
);

function metaLabel(item) {
  if (item.pages) return `${item.format} · ${item.pages} 页`;
  return item.format || "点击阅读";
}

async function open(item) {
  readerTrigger = document.activeElement;
  selected.value = item;
  markdown.value = "";
  loadError.value = "";
  const currentRequest = ++requestId;
  await nextTick();
  if (currentRequest !== requestId) return;
  readerRef.value?.showModal();

  if (item.readType === "markdown") {
    loading.value = true;
    try {
      const response = await fetch(item.readUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const content = await response.text();
      if (currentRequest === requestId) markdown.value = content;
    } catch {
      if (currentRequest === requestId) {
        loadError.value = "内容暂时无法加载，请下载原文件查看。";
      }
    } finally {
      if (currentRequest === requestId) loading.value = false;
    }
  } else {
    loading.value = false;
  }

}

function closeReader() {
  readerRef.value?.close();
  requestId += 1;
  selected.value = null;
  markdown.value = "";
  loadError.value = "";
  loading.value = false;
  readerTrigger?.focus();
}

function handleKeydown(event) {
  if (event.key === "Escape" && selected.value) closeReader();
}

watch(selected, (value) => {
  document.body.style.overflow = value ? "hidden" : "";
});

onMounted(() => window.addEventListener("keydown", handleKeydown));
onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown);
  document.body.style.overflow = "";
});
</script>

<template>
  <div class="sparse-page resource-page">
    <header class="page-head resource-head">
      <div>
        <p class="shiny-kicker">LIBRARY</p>
        <SplitTitle text="资源库" />
        <p class="page-lead">教学大纲、试讲案例与课堂素材。</p>
      </div>
      <div class="resource-summary" aria-label="资源数量">
        <strong>{{ libraryResources.length }}</strong>
        <span>份精选资料</span>
      </div>
    </header>

    <div class="page-scroll">
    <div class="collection-switch" aria-label="资料来源">
      <button type="button" :aria-pressed="collection === 'library'" @click="collection = 'library'">精选资料</button>
      <button type="button" :aria-pressed="collection === 'courses'" @click="collection = 'courses'">课程资源</button>
    </div>
    <CourseResourceCatalog v-if="collection === 'courses'" />
    <div v-if="collection === 'library'" class="resource-toolbar">
      <div class="resource-tabs" role="tablist" aria-label="资源分类">
        <button
          v-for="item in libraryTabs"
          :key="item"
          type="button"
          role="tab"
          :aria-selected="tab === item"
          :class="{ active: tab === item }"
          @click="tab = item"
        >{{ item }}</button>
      </div>
      <button class="reset-layout" type="button" @click="layoutKey += 1">
        重置卡片位置
      </button>
    </div>

    <section v-if="collection === 'library'" class="resource-deck" aria-label="可拖动资源卡片墙">
      <div class="deck-instruction" aria-hidden="true">
        <span>RESOURCE DESK</span>
        <p>拖动调整位置 · 点击查看内容</p>
      </div>

      <DraggableResourceCard
        v-for="item in visible"
        :key="`${layoutKey}-${tab}-${item.id}`"
        :item="item"
        :active="activeCard === item.id"
        @activate="activeCard = $event"
        @open="open"
      />
    </section>

    <section v-if="collection === 'library'" class="resource-board" aria-label="分类资料浏览">
      <header class="resource-board__head">
        <div>
          <p>BROWSE BY TOPIC</p>
          <h2>分类浏览</h2>
        </div>
        <span>封面来自公开图库 · 点击卡片阅读</span>
      </header>
      <div class="resource-board__legend" aria-label="分类数量">
        <span v-for="column in boardColumns" :key="`legend-${column.category}`">
          {{ column.category }} <b>{{ column.items.length }}</b>
        </span>
      </div>
      <div class="resource-board__grid">
        <button
          v-for="item in boardCards"
          :key="`board-${item.id}`"
          type="button"
          class="resource-board-card"
          :data-tone="item.tone"
          @click="open(item)"
        >
          <em>{{ item.category }}</em>
          <strong>{{ item.title }}</strong>
          <p>{{ item.description }}</p>
          <span class="resource-board-card__meta">{{ metaLabel(item) }}</span>
          <span class="resource-board-card__media">
            <img
              :src="boardCoverFor(item)"
              :alt="`${item.title}封面`"
              loading="lazy"
              decoding="async"
            />
            <i aria-hidden="true">+</i>
          </span>
        </button>
      </div>
    </section>

    <p v-if="collection === 'library'" class="resource-note">课题专包与评课说明为训练摘要；官方大纲提供 PDF 预览与原始 Word。非正式国标条目均已在简介中标明。</p>
    </div>

    <Teleport to="body">
      <dialog v-if="selected" ref="readerRef" class="reader-mask" :aria-labelledby="`reader-title-${selected.id}`" @cancel.prevent="closeReader" @mousedown.self="closeReader">
        <section
          class="reader-dialog"
          tabindex="-1"
        >
          <header class="reader-head">
            <div>
              <span>{{ selected.category }} · {{ selected.source }} · {{ selected.year }}</span>
              <h2 :id="`reader-title-${selected.id}`">{{ selected.title }}</h2>
              <p>{{ selected.description }}</p>
            </div>
            <button type="button" aria-label="关闭阅读器" autofocus @click="closeReader">×</button>
          </header>

          <div class="reader-body">
            <iframe
              v-if="selected.readType === 'pdf'"
              :src="selected.readUrl"
              :title="`${selected.title} PDF 预览`"
            />
            <div v-else-if="loading" class="reader-status">正在载入内容...</div>
            <div v-else-if="loadError" class="reader-status is-error">{{ loadError }}</div>
            <MarkdownReader v-else :content="markdown" />
          </div>

          <footer class="reader-foot">
            <span>
              {{ selected.format }}
              <template v-if="selected.pages"> · {{ selected.pages }} 页</template>
            </span>
            <a :href="selected.downloadUrl" :download="selected.downloadName">下载原文件</a>
          </footer>
        </section>
      </dialog>
    </Teleport>
  </div>
</template>

<style scoped>
.resource-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  max-width: none;
  padding-bottom: 0;
  overflow: hidden;
}

.resource-head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  width: 100%;
  max-width: none;
  margin-bottom: 16px;
}

.resource-head :deep(.split-title) {
  font-size: clamp(40px, 4.5vw, 58px);
  letter-spacing: 0;
}

.resource-head .shiny-kicker {
  margin-bottom: 7px;
}

.resource-head .page-lead {
  margin-top: 7px;
  font-size: 14px;
}

.resource-summary {
  display: flex;
  align-items: baseline;
  gap: 9px;
  padding-bottom: 7px;
  color: #8d8691;
}

.resource-summary strong {
  color: #ff9a52;
  font-size: 38px;
  line-height: 1;
}

.resource-summary span {
  font-size: 12px;
  letter-spacing: 0.08em;
}

.resource-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 12px;
}

.resource-tabs {
  display: flex;
  gap: 5px;
  overflow-x: auto;
  padding: 3px;
  scrollbar-width: none;
}

.resource-tabs::-webkit-scrollbar {
  display: none;
}

.resource-tabs button,
.reset-layout {
  flex: 0 0 auto;
  border: 1px solid transparent;
  background: transparent;
  color: #8f8994;
  font-size: 12px;
}

.resource-tabs button {
  padding: 8px 13px;
  border-radius: 8px;
}

.resource-tabs button:hover,
.resource-tabs button.active {
  border-color: rgba(255, 151, 72, 0.35);
  background: rgba(255, 122, 24, 0.1);
  color: #ffd1ad;
}

.reset-layout {
  padding: 8px 0;
  color: #aaa2af;
  text-decoration: underline;
  text-decoration-color: rgba(170, 162, 175, 0.35);
  text-underline-offset: 4px;
}

.reset-layout:hover {
  color: #f1ebf4;
}

.resource-deck {
  position: relative;
  min-height: 420px;
  height: min(48vh, 460px);
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 20px;
  background:
    radial-gradient(circle at 50% 48%, rgba(255, 125, 36, 0.09), transparent 31%),
    linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px),
    #0e0b12;
  background-size: auto, 42px 42px, 42px 42px, auto;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  isolation: isolate;
}

.resource-board {
  margin-top: 22px;
  display: grid;
  gap: 14px;
}

.resource-board__head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
}

.resource-board__head p {
  margin: 0 0 4px;
  color: #9d97a3;
  font-size: 10px;
  letter-spacing: 0.22em;
}

.resource-board__head h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
}

.resource-board__head > span {
  color: #8f8994;
  font-size: 12px;
}

.resource-board__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
}

.resource-board__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #b9b3bd;
  font-size: 12px;
}

.resource-board__legend b {
  min-width: 22px;
  height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.08);
  color: #d8d2dc;
  font-size: 11px;
  font-weight: 600;
}

.resource-board__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  justify-content: start;
}

.resource-board-card {
  width: 100%;
  display: grid;
  gap: 8px;
  padding: 16px 16px 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 22px;
  background: linear-gradient(160deg, rgba(32, 27, 40, 0.92), rgba(14, 11, 18, 0.88));
  color: inherit;
  text-align: left;
  box-shadow: inset 0 1px rgba(255, 255, 255, 0.06);
  transition: border-color 0.2s, transform 0.2s;
}

.resource-board-card:hover,
.resource-board-card:focus-visible {
  border-color: rgba(255, 154, 66, 0.55);
  transform: translateY(-2px);
  outline: none;
}

.resource-board-card em {
  display: inline-flex;
  width: fit-content;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-style: normal;
  letter-spacing: 0.04em;
}

.resource-board-card[data-tone="official"] em {
  color: #ffd1ad;
  background: rgba(255, 122, 24, 0.16);
}
.resource-board-card[data-tone="topic"] em {
  color: #e2beff;
  background: rgba(180, 92, 255, 0.16);
}
.resource-board-card[data-tone="review"] em {
  color: #9fd6ff;
  background: rgba(72, 140, 220, 0.18);
}
.resource-board-card[data-tone="checklist"] em {
  color: #ffc2d8;
  background: rgba(220, 90, 140, 0.16);
}
.resource-board-card[data-tone="case"] em {
  color: #9fe7c8;
  background: rgba(56, 160, 120, 0.16);
}
.resource-board-card[data-tone="external"] em {
  color: #ffe0a3;
  background: rgba(200, 140, 40, 0.16);
}

.resource-board-card strong {
  display: block;
  font-size: 17px;
  line-height: 1.35;
  font-weight: 650;
}

.resource-board-card p {
  margin: 0;
  color: #a9a1ae;
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.resource-board-card__meta {
  color: #8f8994;
  font-size: 12px;
}

.resource-board-card__media {
  position: relative;
  display: block;
  margin-top: 4px;
  border-radius: 16px;
  overflow: hidden;
  background: #1a1520;
  aspect-ratio: 16 / 10;
}

.resource-board-card__media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}

.resource-board-card__media i {
  position: absolute;
  right: 10px;
  bottom: 10px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(255, 182, 150, 0.92);
  color: #1a1010;
  font-style: normal;
  font-size: 22px;
  line-height: 1;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35);
}

.deck-instruction {
  position: absolute;
  top: 50%;
  left: 50%;
  width: min(330px, 80%);
  transform: translate(-50%, -50%);
  color: rgba(215, 208, 219, 0.24);
  text-align: center;
}

.deck-instruction span {
  font-size: 10px;
  letter-spacing: 0.28em;
}

.deck-instruction strong {
  display: block;
  margin-top: 8px;
  font-size: clamp(24px, 4vw, 42px);
  line-height: 1.2;
}

.deck-instruction p {
  margin: 10px 0 0;
  font-size: 12px;
}

.resource-note {
  margin: 8px 4px 0;
  color: #716b76;
  font-size: 11px;
}

.collection-switch { display:flex; gap:8px; margin:0 0 18px; }
.collection-switch button { border:1px solid #ffffff20; border-radius:99px; padding:10px 20px; background:transparent; color:#aaa2af; }
.collection-switch button[aria-pressed="true"] { color:#fff; background:#b65cff22; border-color:#c984ff88; }

.reader-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 24px;
  width:100vw;
  height:100dvh;
  max-width:none;
  max-height:none;
  margin:0;
  border:0;
  background:transparent;
  color:#f4f2f6;
}
.reader-mask::backdrop { background:rgba(6,4,9,.86); backdrop-filter:blur(12px); }

.reader-dialog {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  width: min(1100px, 100%);
  height: min(860px, calc(100vh - 48px));
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 18px;
  outline: none;
  background: #120e17;
  box-shadow: 0 40px 120px rgba(0, 0, 0, 0.72);
}

.reader-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 28px;
  padding: 22px 26px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.reader-head span {
  color: #ffad70;
  font-size: 10px;
  letter-spacing: 0.1em;
}

.reader-head h2 {
  margin: 6px 0 5px;
  color: #f8f4fa;
  font-size: clamp(19px, 2.4vw, 28px);
  line-height: 1.35;
}

.reader-head p {
  margin: 0;
  color: #938b98;
  font-size: 12px;
}

.reader-head button {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
  color: #ddd5e1;
  font-size: 24px;
  line-height: 1;
}

.reader-head button:hover {
  border-color: rgba(255, 151, 72, 0.5);
  color: #ffb67f;
}

.reader-body {
  min-height: 0;
  overflow: auto;
  background: #0c0910;
}

.reader-body iframe {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 520px;
  border: 0;
  background: #ecebea;
}

.reader-status {
  display: grid;
  min-height: 320px;
  place-items: center;
  color: #aaa2ae;
  font-size: 13px;
}

.reader-status.is-error {
  color: #ffaf7c;
}

.reader-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 14px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  color: #817a87;
  font-size: 11px;
}

.reader-foot a {
  padding: 9px 14px;
  border-radius: 8px;
  background: #ff7a18;
  color: #211008;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
}

.reader-fade-enter-active,
.reader-fade-leave-active {
  transition: opacity 0.2s ease;
}

.reader-fade-enter-from,
.reader-fade-leave-to {
  opacity: 0;
}

@media (max-width: 900px) {
  .resource-page {
    display: block;
    height: auto;
    min-height: calc(100dvh - 120px);
    padding-bottom: 32px;
  }

  .resource-head {
    align-items: flex-start;
  }

  .resource-toolbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .resource-tabs {
    width: 100%;
  }

  .resource-deck {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    min-height: 0;
    height: auto;
    padding: 14px;
    overflow: visible;
  }

  .deck-instruction {
    display: none;
  }

  .resource-board__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .resource-board__head {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 620px) {
  .resource-head {
    gap: 16px;
  }

  .resource-summary {
    display: none;
  }

  .resource-deck {
    grid-template-columns: 1fr;
  }

  .resource-board__grid {
    grid-template-columns: 1fr;
  }

  .reader-mask {
    padding: 0;
  }

  .reader-dialog {
    width: 100%;
    height: 100dvh;
    border: 0;
    border-radius: 0;
  }

  .reader-head {
    padding: 18px;
  }

  .reader-head p {
    display: none;
  }

  .reader-foot {
    padding: 12px 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .reader-fade-enter-active,
  .reader-fade-leave-active {
    transition: none;
  }
}
</style>
