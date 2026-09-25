'use strict';
const $ = (selector) => document.querySelector(selector);
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const normalize = (value) => String(value ?? '').normalize('NFKC').toLocaleLowerCase().replace(/\s+/g,' ').trim();
const readableURL = (value) => {try {return decodeURI(value);} catch {return value;}};
const issueLabels = {year_uncertain:'年代含义待核',credit_or_detail_pending:'署名或细节待核',grade_invalid:'原表推荐级异常',public_source_missing:'尚缺公开来源',possible_duplicate_or_variant:'存在相近记录，需辨认版本'};
const statusLabels = {unreviewed:'尚未逐项核验',in_review:'核对中',reviewed:'已核验',disputed:'有争议'};
const state = {query:'',kind:'all',decade:'',language:'',review:'',collection:'',page:1};
const pageSize = 30;
let catalog, entries = [], entryMap = new Map(), collectionMap = new Map(), currentDetail = null;

function filterEntries() {
  const terms = normalize(state.query).split(' ').filter(Boolean);
  let filtered = entries.filter(e => (state.kind === 'all' || e.kind === state.kind)
    && (!state.collection || e.collection_ids.includes(state.collection))
    && (!state.decade || (state.decade === 'unknown' ? e.year === null : Math.floor(e.year / 10) * 10 === Number(state.decade)))
    && (!state.language || e.language === state.language)
    && (!state.review || (state.review === 'issues' ? e.issues.length > 0 : e.review_status === state.review))
    && terms.every(t => e.searchText.includes(t)));
  const q = normalize(state.query);
  const score = e => normalize(e.title) === q ? 100 : e.aliases.some(a => normalize(a) === q) ? 90 : normalize(e.title).includes(q) && q ? 60 : 0;
  filtered.sort((a,b) => score(b)-score(a) || (a.year ?? 9999)-(b.year ?? 9999) || a.title.localeCompare(b.title,'zh-CN') || a.id.localeCompare(b.id));
  return filtered;
}

function renderCollections() {
  const q = normalize($('#collection-search').value);
  $('#collections').innerHTML = catalog.collections.filter(c => normalize(c.title).includes(q)).map(c => `<button type="button" class="collection-button ${state.collection === c.id ? 'active' : ''}" data-collection="${c.id}" aria-pressed="${state.collection === c.id}"><span>${escapeHTML(c.title)}</span><span>${c.entry_ids.length}</span></button>`).join('');
  $('#all-collections').classList.toggle('active', !state.collection);
  $('#all-collections').setAttribute('aria-pressed',String(!state.collection));
}

function render() {
  const selected = collectionMap.get(state.collection);
  $('#page-title').textContent = selected?.title || '声音目录';
  $('#page-description').textContent = selected ? '沿用原整理表的专题收录，条目内容仍待逐项核验。' : '歌曲、原声与配乐，从熟悉的名字开始寻找。';
  const filtered = filterEntries();
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  state.page = Math.min(state.page, pages);
  const start = (state.page - 1) * pageSize;
  $('#result-count').textContent = `${filtered.length.toLocaleString()} 条记录${filtered.length ? ` · 显示 ${start+1}–${Math.min(start+pageSize,filtered.length)}` : ''}`;
  $('#clear-filters').hidden = !(state.query || state.kind !== 'all' || state.decade || state.language || state.review || state.collection);
  $('#results').setAttribute('aria-busy','false');
  $('#results').innerHTML = filtered.length ? filtered.slice(start,start+pageSize).map(e => `<button type="button" class="entry-row" data-entry="${e.id}" aria-label="查看 ${escapeHTML(e.title)}，${escapeHTML(e.artist_credit)} 的详情"><span class="entry-primary"><span class="record-mark" aria-hidden="true">${e.kind === 'bgm' ? '≋' : '♪'}</span><span><span class="entry-title">${escapeHTML(e.title)}</span><span class="entry-artist">${escapeHTML(e.artist_credit || '署名待核')}</span></span></span><span class="entry-secondary"><span class="entry-context">${escapeHTML(e.context || e.album || '关联作品待补充')}</span><span class="tag-list">${e.tags.slice(0,2).map(t => `<span class="tag">${escapeHTML(t)}</span>`).join('')}${e.issues.length ? '<span class="tag issue">有待核问题</span>' : ''}</span></span><span class="entry-year ${e.year === null ? 'unknown' : ''}">${escapeHTML(e.year_label)}</span><span class="row-arrow" aria-hidden="true">↗</span></button>`).join('') : '<div class="empty-state"><strong>还没有匹配的条目</strong><p>可以换一个名称、别名，或减少筛选条件。</p><button type="button" class="text-button" data-reset>查看全部条目</button></div>';
  $('#pagination').innerHTML = filtered.length > pageSize ? `<button type="button" data-page="${state.page-1}" ${state.page === 1 ? 'disabled' : ''}>上一页</button><span>${state.page} / ${pages}</span><button type="button" data-page="${state.page+1}" ${state.page === pages ? 'disabled' : ''}>下一页</button>` : '';
  document.querySelectorAll('[data-kind]').forEach(b => {b.classList.toggle('selected',b.dataset.kind === state.kind);b.setAttribute('aria-pressed',String(b.dataset.kind === state.kind));});
  renderCollections();
}

function showEntry(id) {
  const e = entryMap.get(id);
  currentDetail = id;
  if (!e) {showAbout('这个条目编号暂时不存在。');return;}
  const repo = catalog.repository_url;
  const correction = repo ? `${repo}/issues/new?title=${encodeURIComponent(`条目核对：${e.title} (${e.id})`)}&body=${encodeURIComponent(`条目 ID：${e.id}\n\n需要核对的字段：\n建议内容：\n支持来源（请填写具体页面或资料位置）：\n`)}` : '';
  const section = (title, body) => `<section class="detail-section"><h3>${title}</h3>${body}</section>`;
  const field = (label,value) => `<div><dt>${label}</dt><dd>${escapeHTML(value || '待补充')}</dd></div>`;
  $('#detail-kicker').textContent = e.kind === 'bgm' ? '场景配乐 · SOUND RECORD' : '声音条目 · SOUND RECORD';
  $('#detail-body').innerHTML = `<h2 id="detail-title">${escapeHTML(e.title)}</h2><div class="detail-credit">${escapeHTML(e.artist_credit)}</div><div class="detail-badges"><span class="pending">${statusLabels[e.review_status]}</span><span>${e.audio_refs.length ? '音频由外部存储管理' : '暂无音频关联'}</span>${e.editorial_grade ? `<span>原表推荐 ${e.editorial_grade}</span>` : ''}</div><dl class="detail-grid">${field('原表年代',e.year_label)}${field('语言 / 表达',e.language)}${field('作曲 / 音乐署名',e.composer_credit)}${field('专辑 / 原声',e.album)}${field('关联作品与场景',e.context)}${field('传播载体',e.carriers.join('、'))}</dl><p class="detail-id">${e.id} · 资料修订 ${e.revision}</p>${e.aliases.length ? section('别名与检索入口',`<p>${escapeHTML(e.aliases.join(' / '))}</p>`) : ''}${section('记忆线索',`<div class="tag-list">${e.tags.map(t => `<span class="tag">${escapeHTML(t)}</span>`).join('')}</div>${e.notes ? `<p>${escapeHTML(e.notes)}</p>` : '<p>原表未提供进一步说明，后续可补充收录理由和传播背景。</p>'}`)}${e.issues.length ? section('待核问题',`<ul>${e.issues.map(i => `<li>${escapeHTML(issueLabels[i] || i)}</li>`).join('')}</ul>`) : ''}${section('参考资料',`${e.sources.length ? e.sources.map((s,i) => `<a class="source-link" href="${escapeHTML(s.url)}" target="_blank" rel="noopener noreferrer">${i+1}. ${escapeHTML(new URL(s.url).hostname)} <span aria-hidden="true">↗</span><br><small>${escapeHTML(readableURL(s.url).slice(0,140))}</small></a>`).join('') : '<p>尚无可展示的公开来源。</p>'}<p><small>以上链接来自原整理资料，尚未逐条检查内容和有效性。${escapeHTML(e.year_basis)}。</small></p>`)}${e.related_entry_ids.length ? section('需要对照的相近记录',e.related_entry_ids.map(otherId => {const other = entryMap.get(otherId);return `<p><a href="#entry/${otherId}">${escapeHTML(other.title)} · ${escapeHTML(other.year_label)} · ${escapeHTML(other.artist_credit)}</a></p>`;}).join('')) : ''}${section('所属专题',`<p>${escapeHTML(e.collection_ids.map(c => collectionMap.get(c)?.title).filter(Boolean).join('、') || '总表收录')}</p>`)}${section('导入出处',`<div class="provenance-list">${e.provenance.map(p => `<p>${escapeHTML(p.sheet)} · 第 ${p.row} 行</p>`).join('')}</div><small>完全一致的来源行合并展示，存在差异的记录分别保留。</small>`)}<div class="detail-actions"><button type="button" id="copy-link">复制条目链接</button>${repo ? `<a href="${escapeHTML(correction)}" target="_blank" rel="noopener noreferrer">提出核对建议 ↗</a><a href="${escapeHTML(repo)}/edit/main/data/entries/${e.id}.json" target="_blank" rel="noopener noreferrer">编辑条目 ↗</a>` : ''}</div>`;
  const dialog = $('#detail');
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
}

function showAbout(message = '') {
  currentDetail = null;
  $('#detail-kicker').textContent = '关于这份目录';
  $('#detail-body').innerHTML = `<h2 id="detail-title">留下声音的来处</h2><section class="detail-section">${message ? `<p>${escapeHTML(message)}</p>` : ''}<p>这份目录整理歌曲、影视动画原声与游戏配乐，保留名称、版本、出处和记忆线索。它从已有整理表开始，逐步补充证据与版本关系。</p><p>本次从 ${catalog.source.sheet_count} 张工作表中提取 ${catalog.stats.source_rows.toLocaleString()} 行条目来源，只合并完全一致的记录，形成 ${entries.length.toLocaleString()} 条目录记录。这不等于已经核定的独立作品数。</p><h3>资料正在核对</h3><p>所有导入记录均标记为“尚未逐项核验”。原表推荐级是整理意见，不能代表事实已核实。存在年份、署名或关联差异时，先保留线索。</p><h3>条目与音频分别保存</h3><p>GitHub 只保存目录和核对资料。音频由收藏者另外存储，没有文件的条目仍可检索和补充。这里不托管音频。</p><h3>持续完善</h3><p>条目使用稳定编号。资料修改可以通过仓库提交，核对建议可以附上来源；后续 Agent 的核对结果也通过同一条修订流程进入目录。</p></section>`;
  if (!$('#detail').open) $('#detail').showModal();
  $('#detail').scrollTop = 0;
}

function route() {
  const match = location.hash.match(/^#entry\/(snd-[0-9a-f]{16})$/);
  if (match) showEntry(match[1]);
  else if ($('#detail').open) $('#detail').close();
}
function closeDetail() {$('#detail').close();currentDetail=null;history.replaceState(null,'',location.pathname+location.search);}
function reset() {Object.assign(state,{query:'',kind:'all',decade:'',language:'',review:'',collection:'',page:1});$('#search').value='';['decade','language','review'].forEach(id => $('#'+id).value='');render();}

async function init() {
  try {
    const response = await fetch('./catalog.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    catalog = await response.json();
    entries = catalog.entries.map(e => ({...e,searchText:normalize([e.title,...e.aliases,e.artist_credit,e.composer_credit,e.context,e.album,e.notes,...e.tags,...e.carriers].join(' '))}));
    entryMap = new Map(entries.map(e => [e.id,e]));collectionMap = new Map(catalog.collections.map(c => [c.id,c]));
    $('#total-count').textContent = entries.length.toLocaleString();$('#tab-all').textContent=entries.length.toLocaleString();$('#tab-bgm').textContent=catalog.stats.bgm;$('#collection-count').textContent=catalog.collections.length;
    $('#source-count').textContent = `${catalog.source.label} · ${catalog.stats.source_rows.toLocaleString()} 行来源`;
    if(catalog.repository_url){$('#repo-link').href=catalog.repository_url;$('#repo-link').hidden=false;}
    [...new Set(entries.filter(e => e.year !== null).map(e => Math.floor(e.year / 10)*10))].sort().forEach(d => $('#decade').add(new Option(`${d} 年代`,String(d))));$('#decade').add(new Option('年代待核','unknown'));
    [...new Set(entries.map(e => e.language))].sort((a,b) => a.localeCompare(b,'zh-CN')).forEach(l => $('#language').add(new Option(l,l)));
    render();route();
  } catch(error) {
    $('#result-count').textContent='目录加载失败';$('#results').setAttribute('aria-busy','false');$('#results').innerHTML='<div class="empty-state"><strong>暂时无法读取目录</strong><p>请刷新页面重试，或下载目录文件查看。</p></div>';console.error(error);
  }
}
$('#search-form').addEventListener('submit',e => e.preventDefault());
$('#search').addEventListener('input',e => {state.query=e.target.value;state.page=1;if(catalog)render();});
['decade','language','review'].forEach(id => $('#'+id).addEventListener('change',e => {state[id]=e.target.value;state.page=1;render();}));
$('#collection-search').addEventListener('input',() => {if(catalog)renderCollections();});
$('#all-collections').addEventListener('click',() => {state.collection='';state.page=1;render();});
$('#clear-filters').addEventListener('click',reset);$('#close-detail').addEventListener('click',closeDetail);
$('#detail').addEventListener('cancel',e => {e.preventDefault();closeDetail();});
$('#about-button').addEventListener('click',() => {if(catalog)showAbout();});
document.addEventListener('click',async event => {
  const b = event.target.closest('button');if(!b)return;
  if(b.dataset.entry)location.hash=`entry/${b.dataset.entry}`;
  if(b.dataset.kind){state.kind=b.dataset.kind;state.page=1;render();}
  if(b.dataset.collection){state.collection=b.dataset.collection;state.page=1;render();}
  if(b.dataset.query){state.query=b.dataset.query;$('#search').value=state.query;state.page=1;render();}
  if(b.dataset.page){state.page=Number(b.dataset.page);render();$('#result-count').scrollIntoView({block:'start',behavior:'smooth'});}
  if(b.hasAttribute('data-reset'))reset();
  if(b.id==='copy-link'){try{await navigator.clipboard.writeText(location.href);b.textContent='链接已复制';}catch{b.textContent='请复制浏览器地址栏链接';}}
});
document.addEventListener('keydown',e => {if(e.key==='/'&&!$('#detail').open&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('#search').focus();}});
window.addEventListener('hashchange',route);
init();
