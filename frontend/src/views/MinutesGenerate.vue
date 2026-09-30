<template>
  <div class="minutes-page">
    <div class="page-header">
      <h1>AI 纪要生成</h1>
      <p>选择已完成转写的任务，自动关联会议背景和参考文档，流式生成 AI 纪要</p>
    </div>

    <!-- 表单区 -->
    <div class="form-section">
      <div class="field">
        <label>选择转写任务 <span class="required">*</span></label>
        <el-select v-model="taskId" placeholder="-- 请选择已完成转写的任务 --" style="width: 100%" filterable>
          <el-option v-for="t in tasks" :key="t.id" :value="t.id" :label="t.name || t.id.slice(0, 8)" />
        </el-select>
        <div v-if="taskId && selectedMeeting" class="selected-meeting">
          📋 关联会议：
          <a :href="`/meeting/${selectedMeeting.id}`" target="_blank" class="meeting-link">{{ selectedMeeting.title }}</a>
          <span class="doc-badge">{{ selectedMeeting.snapshot_ids?.length || 0 }} 个文档</span>
        </div>
        <div v-else-if="taskId" class="selected-meeting muted">
          📋 未关联会议，仅使用转写文本生成纪要
        </div>
        <div v-if="taskId && selectedTask" class="selected-task">
          🎙️ 转写任务：
          <a :href="`/task/${taskId}`" target="_blank" class="meeting-link">{{ selectedTask.name || taskId.slice(0, 8) }}</a>
          <span class="doc-badge">查看详情 →</span>
        </div>
      </div>

      <div class="field">
        <label>会议模板</label>
        <div class="template-tabs">
          <el-button
            v-for="t in templates"
            :key="t"
            size="small"
            :type="meetingType === t ? 'primary' : 'default'"
            :title="templateDesc[t]"
            @click="meetingType = t"
          >{{ t }}</el-button>
        </div>
        <div class="template-hint">
          {{ templateDesc[meetingType] }}
          <el-button size="small" text @click="showPrompt = true">查看提示词</el-button>
        </div>
      </div>

      <div class="field">
        <label>使用偏好（可选，可多选）</label>
        <div class="pref-checkbox-list">
          <label v-for="p in adoptedPrefs" :key="p.id" class="pref-checkbox-item">
            <input type="checkbox" :value="p.id" v-model="selectedPrefIds" />
            <span class="pref-checkbox-label">{{ p.name || p.meeting_type }}</span>
            <span v-if="p.is_default" class="default-badge-sm">⭐</span>
            <span v-if="p.notes" class="pref-checkbox-notes">— {{ p.notes }}</span>
          </label>
          <div v-if="!adoptedPrefs.length" class="pref-empty">暂无已采纳偏好，可在偏好管理页面采纳</div>
        </div>
        <div v-if="selectedPrefIds.length" class="pref-hint">
          📎 已选 {{ selectedPrefIds.length }} 个偏好作为参考模板
        </div>
      </div>

      <div class="field">
        <label>自定义提示词（可选，覆盖模板）</label>
        <el-input v-model="customPrompt" type="textarea" :rows="3" placeholder="留空则使用模板默认提示词..." />
      </div>

      <div class="field-row">
        <div class="field">
          <label>
            Temperature
            <span class="tip-icon" data-tip="控制输出随机性：0=严格确定，2=高度随机。纪要生成推荐 0.1-0.5">?</span>
          </label>
          <el-input v-model.number="temperature" type="number" step="0.1" min="0" max="2" />
        </div>
        <div class="field">
          <label>
            Max Tokens
            <span class="tip-icon" data-tip="单次生成最大 Token 数，超出后内容截断。纪要建议 4096-8192">?</span>
          </label>
          <el-input v-model.number="maxTokens" type="number" step="1024" min="256" />
        </div>
      </div>

      <!-- 高级设置：RAG + 验证 -->
      <el-collapse class="advanced-section">
        <el-collapse-item title="⚙️ 高级设置" name="advanced">
          <div class="advanced-row">
            <div class="advanced-item">
              <el-switch v-model="ragEnabled" active-text="启用 RAG 语义检索" />
              <div class="advanced-desc">对参考文档做语义检索 + 重排序，只保留最相关内容</div>
            </div>
            <div class="advanced-item">
              <el-switch v-model="verifyEnabled" active-text="启用质量验证" />
              <div class="advanced-desc">生成后二次调用 LLM 验证幻觉、遗漏和格式</div>
            </div>
          </div>
          <div class="model-chain-hint">
            模型链：<el-tag size="small" type="info">Embedding</el-tag> → <el-tag size="small" type="warning">Reranker</el-tag> → <el-tag size="small" type="success">LLM 生成</el-tag>
            <el-button size="small" text @click="goModelMgmt">管理模型 →</el-button>
          </div>
        </el-collapse-item>
      </el-collapse>

      <div class="form-actions">
        <el-button type="primary" size="large" @click="startGenerate" :disabled="!taskId || generating">
          {{ generating ? '生成中...' : '🚀 生成纪要' }}
        </el-button>
        <el-button v-if="generating" type="danger" @click="stopGenerate">停止</el-button>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="resultText || generating || verifyResult" class="result-section">
      <div class="result-header">
        <h3>生成结果</h3>
        <div class="result-actions">
          <el-button v-if="resultText && !generating && !editing" size="small" @click="startEdit">✏️ 编辑</el-button>
          <el-button v-if="done && !editing" size="small" type="warning" @click="showRegenDialog = true">🔄 重新生成</el-button>
          <el-button v-if="editing" size="small" type="success" @click="doSave" :loading="saving">{{ saving ? '保存中...' : '💾 保存修改' }}</el-button>
          <el-button v-if="editing" size="small" @click="cancelEdit">取消</el-button>
          <el-button v-if="resultText" size="small" @click="copyResult">📋 复制</el-button>
          <span v-if="usage" class="usage-info">Token: {{ usage }}</span>
          <router-link v-if="done" to="/minutes">
            <el-button size="small" type="primary">📋 查看列表</el-button>
          </router-link>
          <el-button v-if="done && !editing" size="small" @click="resetForm">🔄 继续生成</el-button>
        </div>
      </div>

      <!-- 阶段指示器 -->
      <div v-if="phaseMessage && generating" class="phase-indicator">
        <div class="spinner-small"></div>
        <span>{{ phaseMessage }}</span>
      </div>

      <!-- 验证/修正状态消息（不混入正文） -->
      <div v-if="statusMessage && generating" class="status-bar">
        <span>{{ statusMessage }}</span>
      </div>

      <!-- 质量验证结果（Element Plus 手风琴） -->
      <div v-if="verifyResult" class="verify-card">
        <div class="verify-header" @click="toggleVerifyCollapse">
          <span class="verify-icon">🔍</span>
          <span class="verify-title">质量验证结果</span>
          <span class="verify-score" :class="scoreClass(verifyResult.score)">
            {{ verifyResult.score }}/100
          </span>
          <el-icon class="collapse-icon" :class="{ rotated: verifyExpanded }"><ArrowDown /></el-icon>
        </div>
        <el-collapse v-model="verifyActivePanel" accordion>
          <el-collapse-item name="issues" title="⚠️ 问题列表">
            <div v-if="verifyResult.issues?.length">
              <div v-for="(issue, i) in verifyResult.issues" :key="i" class="verify-issue-item">
                <span class="issue-severity" :class="severityClass(issue.severity)">{{ issue.severity || '一般' }}</span>
                {{ issue.text || issue }}
              </div>
            </div>
            <div v-else class="verify-no-issues">✅ 未检测到明显问题</div>
          </el-collapse-item>
          <el-collapse-item v-if="verifyResult.suggestions?.length" name="suggestions" title="💡 改进建议">
            <div v-for="(s, i) in verifyResult.suggestions" :key="i" class="verify-suggestion-item">• {{ s.text || s }}</div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div class="result-body" ref="resultBody">
        <div v-if="!resultText && generating" class="generating-status">
          <div class="spinner"></div>
          <span>正在生成纪要，请稍候...</span>
        </div>
        <div v-if="editing" class="edit-area">
          <el-input v-model="editText" type="textarea" :rows="20" @input="onEditInput" />
          <div class="edit-hint">支持 Markdown 格式，修改后点击「保存修改」</div>
        </div>
        <div v-else class="markdown-content" v-html="renderedResult"></div>
        <div v-if="generating && resultText" class="cursor-blink">▍</div>
        <div v-if="done && !editing" class="done-banner">✅ 纪要生成完成</div>
      </div>
    </div>

    <!-- 重新生成弹窗 -->
    <el-dialog v-model="showRegenDialog" title="🔄 重新生成纪要" width="520px" :close-on-click-modal="false">
      <div class="field">
        <label>修改原因 <span class="required">*</span></label>
        <el-select v-model="regenReason" placeholder="-- 请选择 --" style="width: 100%">
          <el-option value="内容不准确" label="内容不准确" />
          <el-option value="遗漏关键信息" label="遗漏关键信息" />
          <el-option value="格式不符合要求" label="格式不符合要求" />
          <el-option value="决策描述不清晰" label="决策描述不清晰" />
          <el-option value="其他" label="其他" />
        </el-select>
      </div>
      <div class="field">
        <label>注意事项</label>
        <el-input v-model="regenNotes" type="textarea" :rows="4" placeholder="输入你的具体要求，如：请重点关注待办事项的截止时间、把决策描述得更详细等" />
      </div>
      <div class="field">
        <label>使用偏好（可多选）</label>
        <div class="pref-checkbox-list">
          <label v-for="p in adoptedPrefs" :key="p.id" class="pref-checkbox-item">
            <input type="checkbox" :value="p.id" v-model="regenPrefIds" />
            <span class="pref-checkbox-label">{{ p.name || p.meeting_type }}</span>
            <span v-if="p.is_default" class="default-badge-sm">⭐</span>
          </label>
          <div v-if="!adoptedPrefs.length" class="pref-empty">暂无已采纳偏好</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showRegenDialog = false">取消</el-button>
        <el-button type="primary" @click="doRegenerate" :disabled="!regenReason || regenerating" :loading="regenerating">
          🚀 重新生成
        </el-button>
      </template>
    </el-dialog>

    <!-- 提示词预览弹窗 -->
    <el-dialog v-model="showPrompt" :title="`提示词模板：${meetingType}`" width="720px">
      <div class="prompt-hint">以下是 AI 使用的系统提示词。你可以参考此格式，在「自定义提示词」中覆盖修改。</div>
      <pre class="prompt-body">{{ templatePrompts[meetingType] }}</pre>
      <template #footer>
        <el-button @click="copyPrompt">📋 复制</el-button>
        <el-button type="primary" @click="showPrompt = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { listTasks, listMeetings, updateMinutes, listPreferences } from '../api.js'
import { marked } from 'marked'
import { toast } from '../toast.js'
import { ArrowDown } from '@element-plus/icons-vue'

marked.setOptions({ breaks: true, gfm: true })

const tasks = ref([])
const meetings = ref([])
const meetingMap = ref({})
const taskId = ref('')
const meetingType = ref('通用')
const customPrompt = ref('')
const temperature = ref(0.3)
const maxTokens = ref(16384)
const templates = ['通用', '需求评审', '技术评审', '周会']
const templateDesc = {
  '通用': '动态模块：会议摘要、已达成决策、待办事项、讨论议题、变更记录（有参考文档时）',
  '需求评审': '动态模块：评审结论、已达成决策、待办事项、讨论分歧、变更记录（有参考文档时）',
  '技术评审': '动态模块：技术方案结论、技术决策、待办事项、技术分歧、架构变更（有参考文档时）',
  '周会': '动态模块：上周进展、本周计划、待办事项、关键决策、风险阻塞',
}
const templatePrompts = {
  '通用': `你是一位专业的会议纪要撰写专家。请根据【会议转写文本】生成结构化的会议纪要。

## 核心原则

0. **直接输出**：严禁输出任何开头语、解释、说明或结束语，直接输出会议纪要正文；
1. **仅源于会议**：每条决策、待办、议题都必须在转写文本中有对应的原话依据。转写文本中找不到依据的，**严禁写入**；
2. **文档隔离**：参考文档内容**只能**出现在「变更记录」模块。决不允许把文档内容当作「已达成决策」输出；
3. **口头讨论优先**：口头结论与文档冲突时，以口头为准并在变更记录中标注；
4. **过滤噪音**：过滤闲聊、寒暄、跑题，只保留有效业务信息。

## 输出模块（动态展示，有内容才输出，无内容则跳过）

### 会议摘要
（用 100-250 字概括本次会议核心内容：讨论目标、主要进展、关键结论，不要复述细节）

### 已达成决策
- **{决策项}**：{决策内容}（决策人：{角色/姓名}）
- 每项用 "- **标题**：内容（决策人：xxx）" 格式

### 待办事项
- {待办描述} @{责任人} 截止：{截止时间}
- 每项用 "- {描述} @{角色} 截止：{时间}" 格式

### 讨论议题
> 客观记录议题讨论过程，无则跳过此模块
- **{议题}**：{讨论内容}

### 变更记录
> 仅在有参考文档时输出，无参考文档则跳过此模块
- **变更项**：xxx
- **原内容**：xxx
- **现内容**：xxx

### 会议参与人
- {角色/姓名}（{角色说明}）

## 关键提取规则

**待办提取**：转写文本中出现以下关键词的语句，优先提取为待办：
「需要」「要」「必须」「负责」「跟进」「确认」「安排」「决定」「待定」「考虑」「评估」「调研」「优化」「修改」「调整」「推动」「落实」

**责任人推断**：
- 优先从上下文找具体人名
- 其次推断角色
- 完全找不到时写「待确认」，禁止使用「【未指定责任人】」

**参会人推断**：
- 从「XX说」「XX认为」「XX觉得」「XX提到」等句式提取人名
- 结合上下文推断角色
- 找不到具体人名时根据讨论内容推断角色

## 输出示例

\`\`\`
### 会议摘要
本次会议主要讨论了 Q3 用户增长策略，明确了上线前的三个关键节点：A/B 测试方案设计、多渠道推广渠道对接、数据埋点验收。

### 已达成决策
- **A/B 测试方案**：采用客户端分桶方案，流量按 1:1 分流，决策人：产品负责人
- **灰度节奏**：先 10% 内测 3 天 → 全量开放，决策人：技术负责人

### 待办事项
- 输出 A/B 测试详细方案 @产品经理 截止：周五
- 完成数据埋点设计文档 @后端开发 截止：周四
- 准备推广渠道对接技术方案 @前端开发 截止：下周一

### 会议参与人
- 张总（产品负责人）
- 李明（技术负责人）
- 王芳（数据分析）
- 赵岩（后端开发）
\`\`\``,

  '需求评审': `你是一个专业的会议纪要助手，负责将会议转写文本整理为结构化的需求评审纪要。

## 输入说明
【会议转写文本】：下面转录的会议口头对话内容，优先级最高
【参考文档】：可选，作为业务基线；本次若无参考文档，则变更记录章节直接填：无参考文档，不输出变更对比

## 核心约束（必须严格遵守）
0. **直接输出**：严禁输出任何开头语、解释、说明或结束语，直接输出会议纪要正文；
1. **仅源于会议**：每条决策、待办、分歧都必须在转写文本中有对应原话，严禁编造；
2. **文档隔离**：参考文档内容**只能**出现在「变更记录」模块，决不允许当成决策/待办输出；
3. 会议口头讨论优先级高于参考文档，二者发生冲突时以会议口头结论为准，并在变更记录中标注该变更；
4. 识别不到责任人统一标记【未指定责任人】，识别不到截止时间统一标记【时间待确认】，禁止自行编造人名与时间；
5. 过滤闲聊、跑题、寒暄内容，只保留有效业务评审信息；
6. ⚠️ **表格一致性规则（严格遵循）**：
   a. 评审结论写「未形成明确评审结论」时，"### 关键决策"标题必须改为"### 讨论方案汇总（待后续确认）"，且表格必须在「决策人」后增加「状态」列（值填"待确认"或"已确认"），严禁使用"关键决策"这个说法避免矛盾；
   b. 任一张表格**无内容**时，不能只填"无"或留空，须在表头下方加说明行，格式为：\`> 本次会议暂未涉及相关内容，无对应信息可填写\`；
   c. 待办事项表格中，如果所有行的「责任人」和「截止时间」都是占位符，须在表格末尾加行说明：\`> ⚠️ 以上待办均未在会议中明确责任人和截止时间，需会后补充确认\`；
   d. 风险与问题表格如果全部为「无」，须替换为：\`> 本次会议未识别出风险与问题，无需处理\`；
7. 无法从文本提取会议主题，填写【未识别会议主题】；无法提取业务背景，填写「从会议文本中未获取业务背景」；
8. 区分三类信息：①已拍板决策 ②讨论过但未达成共识 ③待执行待办，不可互相混淆。
	9. ⚠️ **讨论方案汇总填写规则（严禁填"无"）**：
	   评审结论写「未形成明确评审结论」时，"### 讨论方案汇总（待后续确认）"表格必须遵守：
	   a. 只要会上对某个议题进行了讨论（不论是否达成结论），就必须在表中列出；
	   b. 状态填「待确认」或「已确认」；
	   c. **错误示例**（会扣分）：整表填"无" ❌
	   d. **正确示例**（应得分）：
	      | 议题 | 讨论内容 | 决策人 | 状态 |
	      |------|---------|--------|------|
	      | 奖品规格确认 | 讨论了去年方案与其他方案的差异，未达成一致 | 待确认 | 待确认 |
	      | 推广时间排期 | 讨论了9月排期安排 | 运营 | 待确认 |
	10. ⚠️ **待办事项填写规则（严禁填"无"）**：
	    a. 从转写文本中提取所有包含以下关键词的内容：「需要」「要」「必须」「负责」「跟进」「安排」「确认」「决定」「待定」「考虑」「评估」「调研」；
	    b. 每个关键词关联的内容必须形成一条待办，责任人找不到填「待确认」而非「【未指定责任人】」；
	    c. 截止时间不确定也填「待确认」，严禁填「无」；
	    d. 待办与未决议题不矛盾：未决议题 = 待讨论的议题，待办 = 需要有人去推进/确认的行动项，同一个议题可能同时出现在两个表中；
	11. **会议参与人填写规则**：
	    a. 从转写文本中提取所有人名、角色称呼（产品/运营/开发/设计/测试/项目经理等）；
	    b. 如果无法提取具体姓名，至少根据讨论内容推断参与角色，如「产品经理、运营、开发（具体姓名待确认）」；
	    c. 严禁直接写「未从会议文本识别参会人员」——文本中至少能推断出有几方角色在发言。

## 输出格式（严格使用Markdown，不要额外增加模块）

### 会议基本信息
- **会议主题**：{meeting_title}
- **会议类型**：需求评审
- **业务背景**：{background}

### 评审结论
（输出本次需求评审的最终结论：通过 / 不通过 / 有条件通过；如果会上未给出明确评审结论，输出：「本次会议未形成明确评审结论，需后续继续评审」）

### 讨论分歧点
> 逐条记录会上各方不同意见、争议点，每条一行，格式：\`- 【议题】争议方A认为…，争议方B认为…\`

### 讨论方案汇总（待后续确认）
> 当评审结论为「未形成明确评审结论」时，此标题替代"关键决策"。**只要会议上讨论过的议题都必须列出，不能填"无"。**
| 议题 | 讨论内容 | 决策人 | 状态 |
|------|---------|--------|------|

### 待办事项
> 从转写文本中提取所有需跟进的内容，**即使未指定责任人和时间也要列出行、填"待确认"**。
| 待办项 | 责任人 | 截止时间 | 备注 |
|--------|--------|---------|------|

### 风险与问题
| 风险/问题 | 影响 | 建议方案 |
|----------|------|---------|

### 未决议题
> 会上进行了讨论，但暂未得出最终结论，需要后续继续跟进的事项

### 变更记录
> 与参考文档不一致的变更点，以会议口头讨论为准；无参考文档则填写：无参考文档，不输出变更对比

### 会议参与人
（根据会议讨论中提到的参与人整理；至少推断出参与角色，如「产品经理、运营、开发（具体姓名待确认）」；严禁直接写"未从会议文本识别参会人员"）`,

    '技术评审': `你是一位专业的会议纪要撰写专家。请根据【会议转写文本】生成结构化的技术评审纪要。

## 核心原则

0. **直接输出**：严禁输出任何开头语、解释、说明或结束语，直接输出会议纪要正文；
1. **仅源于会议**：每条决策、待办、分歧都必须在转写文本中有对应原话，严禁编造；
2. **文档隔离**：参考文档内容**只能**出现在「架构变更」模块，决不允许当成技术决策输出；
2. **参考文档仅做基线**：文档有但会上未讨论的内容，严禁输出评审结论；
3. **口头讨论优先**：口头结论与文档冲突时，以口头为准，并在架构变更中标注；
4. **过滤噪音**：过滤闲聊、跑题、寒暄，只保留有效技术评审信息。

## 输出模块（动态展示，有内容才输出，无内容则跳过）

### 技术方案评审结论
（一句话结论：通过 / 不通过 / 修改后通过；未形成结论则写「本次会议未形成明确技术评审结论，需后续继续评审」）

### 已达成技术决策
- **{决策项}**：{决策内容}（决策人：{角色/姓名}）
- 每项用 "- **标题**：内容（决策人：xxx）" 格式

### 待办事项
- {待办描述} @{责任人} 截止：{截止时间}
- 每项用 "- {描述} @{角色} 截止：{时间}" 格式

### 技术分歧 & 未决议题
> 客观记录各方技术争议点、讨论过但暂未达成结论的问题，无则跳过此模块

### 架构变更
> 仅在有参考文档时输出，无参考文档则跳过此模块
- **变更项**：xxx
- **原方案**：xxx
- **现方案**：xxx
- **原因**：xxx

### 技术风险
> 识别到的技术风险项，无则跳过此模块
- **风险**：xxx，**影响**：xxx，**应对**：xxx

### 会议参与人
- {角色/姓名}（{角色说明}）

## 关键提取规则

**待办提取**：转写文本中出现以下关键词的语句，优先提取为待办：
「需要」「要」「必须」「负责」「跟进」「确认」「安排」「决定」「待定」「考虑」「评估」「调研」「优化」「修改」「调整」「重构」「兼容」「迁移」「推动」「落实」

**责任人推断**：
- 优先从上下文找具体人名
- 其次推断角色（架构师 / 后端开发 / 前端开发 / QA / DBA 等）
- 完全找不到时写「待确认」，禁止使用「【未指定责任人】」

**参会人推断**：
- 从「XX说」「XX认为」「XX提到」等句式提取人名
- 结合上下文推断技术角色

## 输出示例

\`\`\`
### 技术方案评审结论
有条件通过，需补充数据迁移方案和回滚策略后再次评审。

### 已达成技术决策
- **数据库选型**：从 MySQL 迁移至 PostgreSQL，决策人：后端架构师
- **缓存方案**：采用 Redis Cluster，淘汰原 Memcached 方案，决策人：技术负责人

### 待办事项
- 输出数据迁移方案，包含回滚策略 @后端架构师 截止：9月5日
- 评估 PostgreSQL 兼容性，对齐现有 ORM 层 @后端开发 截止：9月3日
- 准备性能对比测试报告 @QA 截止：9月7日

### 技术分歧 & 未决议题
> 关于消息队列选型，架构师推荐 RocketMQ，开发团队倾向 RabbitMQ（团队更熟悉），待 POC 测试后决定。

### 架构变更
- **变更项**：数据库
- **原方案**：MySQL 5.7
- **现方案**：PostgreSQL 15
- **原因**：评审会上一致认为现有 MySQL 在 JSON 查询和全文检索场景下性能瓶颈明显

### 会议参与人
- 陈总（技术负责人）
- 刘工（后端架构师）
- 小周（后端开发）
- 林姐（QA）
\``,

  '周会': `你是一位专业的会议纪要撰写专家。请根据【会议转写文本】生成结构化的周会纪要。

## 核心原则

0. **直接输出**：严禁输出任何开头语、解释、说明或结束语，直接输出会议纪要正文；
1. **仅源于会议**：每条进展、计划、决策都必须在转写文本中有对应原话，严禁编造；
2. **客观复述**：各成员同步的进展用条目化客观复述，不要主观加工或评价；
3. **过滤噪音**：过滤闲聊、寒暄、跑题，只保留有效业务信息；
4. **周会一般无参考文档**，变更记录模块不输出。

## 输出模块（动态展示，有内容才输出，无内容则跳过）

### 上周进展
- {项目/模块}：{完成事项}（负责人：{角色/姓名}）
- 按项目或模块分组，每条 "- {内容}（负责人：xxx）"

### 本周计划
- {项目/模块}：{计划事项}（负责人：{角色/姓名}）
- 按项目或模块分组，每条 "- {内容}（负责人：xxx）"

### 关键决策
> 周会过程中临时敲定的决议，无则跳过此模块
- **{决策项}**：{决策内容}（{角色/姓名}）

### 待办事项
- {待办描述} @{责任人} 截止：{截止时间}
- 每项用 "- {描述} @{角色} 截止：{时间}" 格式

### 风险与阻塞
> 识别到的风险或阻塞项，无则跳过此模块
- **{风险/阻塞}**：{描述}，责任人：{角色}，需要支持：{事项}

### 会议参与人
- {角色/姓名}（{角色说明}）

## 关键提取规则

**待办提取**：转写文本中出现以下关键词的语句，优先提取为待办：
「需要」「要」「必须」「负责」「跟进」「确认」「安排」「决定」「待定」「考虑」「评估」「调研」「优化」「修改」「调整」「推动」「落实」「赶」「这周出」「下周完成」

**责任人推断**：
- 优先从上下文找具体人名
- 其次推断角色
- 完全找不到时写「待确认」，禁止使用「【未指定责任人】」

## 输出示例

\`\`\`
### 上周进展
- 用户管理模块：完成列表页重构和权限联调（负责人：赵岩）
- 数据报表：完成 PV/UV 看板开发，已提测（负责人：王芳）
- 性能优化：数据库慢查询已定位 3 条，正在优化中（负责人：刘工）

### 本周计划
- 用户管理模块：补充审批流异常处理（负责人：赵岩）
- 数据报表：修复测试反馈的 2 个 bug，周三前提测（负责人：王芳）
- 性能优化：完成慢查询优化并上线（负责人：刘工）

### 待办事项
- 修复用户权限缓存不同步问题 @赵岩 截止：本周三
- 配合测试完成报表回归测试 @王芳 截止：本周四
- 输出数据库索引优化方案 @刘工 截止：本周五

### 会议参与人
- 李明（技术负责人）
- 赵岩（后端开发）
- 王芳（测试/全栈）
- 刘工（架构师）
\``,
}
const showPrompt = ref(false)

const generating = ref(false)
const done = ref(false)
const router = useRouter()
const route = useRoute()
const resultText = ref('')
const usage = ref(null)
const abortController = ref(null)
const resultBody = ref(null)
const pendingBuffer = ref('')
let typingTimer = null
// 编辑相关
const recordId = ref(null)
const editing = ref(false)
const editText = ref('')
const saving = ref(false)
// 偏好相关
const adoptedPrefs = ref([])
const selectedPrefIds = ref([])
// RAG + 验证（从 localStorage 加载工作流配置）
const workflowCfg = JSON.parse(localStorage.getItem('workflow_config') || '{}')
const ragEnabled = ref(workflowCfg.rag_enabled ?? false)
const verifyEnabled = ref(workflowCfg.verify_enabled ?? false)
const phaseMessage = ref('')
const statusMessage = ref('')
const verifyResult = ref(null) // { score, issues, suggestions }
const verifyActivePanel = ref('issues')
const verifyExpanded = computed(() => !!verifyActivePanel.value)
function toggleVerifyCollapse() {
  verifyActivePanel.value = verifyExpanded.value ? '' : 'issues'
}
// 重新生成弹窗
const showRegenDialog = ref(false)
const regenReason = ref('')
const regenNotes = ref('')
const regenPrefIds = ref([])
const regenerating = ref(false)

const selectedMeeting = computed(() => {
  const t = tasks.value.find(t => t.id === taskId.value)
  if (!t || !t.meeting_id) return null
  return meetings.value.find(m => m.id === t.meeting_id) || null
})

const selectedTask = computed(() => {
  return tasks.value.find(t => t.id === taskId.value) || null
})

const selectedPref = computed(() => {
  if (!selectedPrefIds.value.length) return null
  return adoptedPrefs.value.filter(p => selectedPrefIds.value.includes(p.id))
})

const renderedResult = computed(() => {
  if (!resultText.value) return ''
  try {
    let html = marked.parse(resultText.value)
    html = html.replace(/<img src="https:\/\/cdn\.nlark\.com([^"]+)"/g, (match, path) => {
      const origUrl = `https://cdn.nlark.com${path}`
      return `<img src="/api/yuque-image-proxy?url=${encodeURIComponent(origUrl)}"`
    })
    return html
  } catch {
    return resultText.value
  }
})

onMounted(async () => {
  try {
    const res = await listTasks({ task_type: 'asr', limit: 50 })
    tasks.value = res.records || res
    // 如果 URL 带了 task_id 参数，自动选中
    const urlTaskId = route.query.task_id
    if (urlTaskId && tasks.value.some(t => t.id === urlTaskId)) {
      taskId.value = urlTaskId
    }
  } catch { /* ignore */ }
  try {
    meetings.value = (await listMeetings()).records || []
    const map = {}
    for (const m of meetings.value) map[m.id] = m.title
    meetingMap.value = map
  } catch { /* ignore */ }
  // 加载已采纳偏好
  try {
    const res = await listPreferences({ adopted: 1 })
    adoptedPrefs.value = (res.preferences || [])
    // 如果有默认偏好，自动选中
    const defaultPrefs = adoptedPrefs.value.filter(p => p.is_default)
    if (defaultPrefs.length) {
      selectedPrefIds.value = defaultPrefs.map(p => p.id)
    }
  } catch { /* ignore */ }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

watch(resultText, () => {
  nextTick(() => {
    if (resultBody.value) {
      resultBody.value.scrollTop = resultBody.value.scrollHeight
    }
  })
})

async function startGenerate(regenOpts) {
  if (!taskId.value) return
  generating.value = true
  done.value = false
  resultText.value = ''
  usage.value = null
  pendingBuffer.value = ''
  if (typingTimer) { clearInterval(typingTimer); typingTimer = null }

  const params = new URLSearchParams({ task_id: taskId.value })
  if (meetingType.value) params.set('meeting_type', meetingType.value)
  if (customPrompt.value.trim()) params.set('custom_prompt', customPrompt.value.trim())
  params.set('temperature', String(temperature.value))
  params.set('max_tokens', String(maxTokens.value))
  if (ragEnabled.value) params.set('rag_enabled', '1')
  if (verifyEnabled.value) params.set('verify_enabled', '1')

  // 偏好与重新生成参数
  const prefIds = regenOpts?.prefIds?.length ? regenOpts.prefIds : selectedPrefIds.value
  if (prefIds.length) params.set('preference_ids', prefIds.join(','))
  if (regenOpts?.reason) params.set('regenerate_reason', regenOpts.reason)
  if (regenOpts?.notes) params.set('regenerate_notes', regenOpts.notes)

  abortController.value = new AbortController()
  const token = localStorage.getItem('auth_token')

  // 打字机效果：每 35ms 从 pendingBuffer 取出一个字符显示
  typingTimer = setInterval(() => {
    if (pendingBuffer.value.length > 0) {
      resultText.value += pendingBuffer.value[0]
      pendingBuffer.value = pendingBuffer.value.slice(1)
    }
  }, 35)

  try {
    const resp = await fetch(`/api/minutes/generate?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: abortController.value.signal,
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: '请求失败' }))
      resultText.value = `错误: ${err.detail || resp.statusText}`
      generating.value = false
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done: streamDone, value } = await reader.read()
      if (streamDone) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6).trim()
        if (!dataStr) continue
        try {
          const data = JSON.parse(dataStr)
          if (data.type === 'chunk') {
            pendingBuffer.value += data.text
          } else if (data.type === 'phase') {
            phaseMessage.value = data.message || ''
            if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
          } else if (data.type === 'verify') {
            phaseMessage.value = '✅ 质量验证完成'
            verifyResult.value = {
              score: data.score,
              issues: data.issues || [],
              suggestions: data.suggestions || [],
            }
          } else if (data.type === 'status') {
            statusMessage.value = data.message || ''
          } else if (data.type === 'done') {
            // 完成：先清空 pendingBuffer，再标记 done
            statusMessage.value = ''
            if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
            // 立即显示剩余内容
            resultText.value += pendingBuffer.value
            pendingBuffer.value = ''
            resultText.value = data.text
            recordId.value = data.id
            if (data.preference_id) {
              // 刷新偏好列表
              try {
                const res = await listPreferences({ adopted: 1 })
                adoptedPrefs.value = (res.preferences || [])
              } catch { /* ignore */ }
            }
            if (data.usage) usage.value = data.usage.total_tokens
            generating.value = false
            done.value = true
            await nextTick()
            if (resultBody.value) {
              resultBody.value.scrollTop = resultBody.value.scrollHeight
            }
          } else if (data.type === 'error') {
            if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
            statusMessage.value = ''
            resultText.value += pendingBuffer.value
            pendingBuffer.value = ''
            resultText.value = `错误: ${data.message}`
            generating.value = false
          }
        } catch { /* ignore */ }
      }
    }
  } catch (e) {
    if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
    resultText.value += pendingBuffer.value
    pendingBuffer.value = ''
    if (e.name === 'AbortError') {
      resultText.value += '\n\n--- 已停止 ---'
    } else {
      resultText.value = `错误: ${e.message}`
    }
  } finally {
    generating.value = false
  }
}

function stopGenerate() {
  if (abortController.value) {
    abortController.value.abort()
  }
  if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
  resultText.value += pendingBuffer.value
  pendingBuffer.value = ''
}

function resetForm() {
  if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
  resultText.value = ''
  usage.value = null
  done.value = false
  generating.value = false
  abortController.value = null
  pendingBuffer.value = ''
  recordId.value = null
  editing.value = false
  editText.value = ''
  showRegenDialog.value = false
  regenReason.value = ''
  regenNotes.value = ''
  regenPrefIds.value = []
  phaseMessage.value = ''
  verifyResult.value = null
}

function goModelMgmt() {
  router.push('/models')
}

function scoreClass(score) {
  if (!score && score !== 0) return ''
  if (score >= 80) return 'score-good'
  if (score >= 60) return 'score-ok'
  return 'score-bad'
}

function severityClass(severity) {
  if (!severity) return ''
  const map = { 严重: 'sev-critical', 一般: 'sev-normal', 轻微: 'sev-minor' }
  return map[severity] || ''
}

// 重新生成
function doRegenerate() {
  if (!regenReason.value) return
  showRegenDialog.value = false
  regenerating.value = true
  startGenerate({
    reason: regenReason.value,
    notes: regenNotes.value,
    prefIds: regenPrefIds.value.length ? regenPrefIds.value : selectedPrefIds.value,
  })
  regenerating.value = false
}

// 编辑功能
function startEdit() {
  editText.value = resultText.value
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  editText.value = ''
}

function onEditInput() {
  // 实时更新预览
  resultText.value = editText.value
}

async function doSave() {
  if (!recordId.value || !editText.value.trim()) return
  saving.value = true
  try {
    await updateMinutes(recordId.value, { content: editText.value })
    resultText.value = editText.value
    editing.value = false
    toast.success('保存成功！')
  } catch (e) {
    toast.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(resultText.value)
    toast.success('已复制到剪贴板')
  } catch {
    const ta = document.createElement('textarea')
    ta.value = resultText.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(templatePrompts[meetingType.value])
    toast.success('提示词已复制')
  } catch {
    const ta = document.createElement('textarea')
    ta.value = templatePrompts[meetingType.value]
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}
</script>

<style scoped>
.minutes-page { padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.form-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 24px; margin-bottom: 24px; max-width: 800px; }
.field { margin-bottom: 16px; flex: 1; }
.field label { display: block; font-size: 0.85rem; color: #64748b; margin-bottom: 4px; }
.field .required { color: #dc2626; }
.form-select, .form-input { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; box-sizing: border-box; }
.form-select:focus, .form-input:focus { border-color: #4f46e5; }
.form-textarea { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; box-sizing: border-box; font-family: inherit; resize: vertical; }
.form-textarea:focus { border-color: #4f46e5; }
.field-row { display: flex; gap: 14px; }

/* ? 图标悬浮提示 */
.tip-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; border-radius: 50%;
  background: #cbd5e1; color: #fff; font-size: 0.65rem; font-weight: 700;
  cursor: help; vertical-align: middle; margin-left: 4px;
  position: relative; user-select: none;
  z-index: 1;
}
.tip-icon:hover { background: #94a3b8; }
.tip-icon::after {
  content: attr(data-tip);
  position: absolute; top: calc(100% + 6px); left: 0;
  background: #1e293b; color: #fff;
  font-size: 0.72rem; font-weight: 400; white-space: nowrap;
  padding: 5px 10px; border-radius: 6px;
  pointer-events: none; opacity: 0; transition: opacity 0.15s;
  z-index: 9999; line-height: 1.4;
}
.tip-icon:hover::after { opacity: 1; }

.selected-meeting { margin-top: 8px; padding: 8px 12px; background: #eef2ff; border-radius: 6px; font-size: 0.85rem; color: #4f46e5; }
.selected-meeting.muted { background: #f1f5f9; color: #94a3b8; }
.selected-task { margin-top: 6px; padding: 8px 12px; background: #f0fdf4; border-radius: 6px; font-size: 0.85rem; color: #16a34a; }
.meeting-link { color: #4f46e5; text-decoration: underline; cursor: pointer; }
.meeting-link:hover { color: #4338ca; }
.doc-badge { font-size: 0.75rem; background: #fff; padding: 1px 6px; border-radius: 3px; margin-left: 6px; }

.template-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.template-hint { margin-top: 6px; font-size: 0.78rem; color: #94a3b8; padding: 4px 8px; background: #f8fafc; border-radius: 4px; display: flex; align-items: center; gap: 8px; }

.form-actions { display: flex; gap: 12px; margin-top: 8px; }

/* 结果区 */
.result-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.result-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; border-bottom: 1px solid #e2e8f0; background: #f8fafc; flex-wrap: wrap; gap: 8px; }
.result-header h3 { margin: 0; font-size: 0.95rem; color: #1e293b; }
.result-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.usage-info { font-size: 0.78rem; color: #94a3b8; white-space: nowrap; }
.result-body { padding: 20px 24px; max-height: 600px; overflow-y: auto; }

/* Markdown 渲染 */
.markdown-content { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif; font-size: 15px; line-height: 1.8; color: #262626; word-wrap: break-word; }
.markdown-content :deep(h1) { font-size: 1.6em; font-weight: 600; margin: 1.2em 0 0.5em; padding-bottom: 0.3em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.markdown-content :deep(h2) { font-size: 1.4em; font-weight: 600; margin: 1em 0 0.4em; padding-bottom: 0.2em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.markdown-content :deep(h3) { font-size: 1.2em; font-weight: 600; margin: 0.8em 0 0.3em; color: #1a1a1a; }
.markdown-content :deep(p) { margin: 0.5em 0; }
.markdown-content :deep(strong) { font-weight: 600; color: #1a1a1a; }
.markdown-content :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
.markdown-content :deep(th), .markdown-content :deep(td) { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
.markdown-content :deep(th) { background: #f6f8fa; font-weight: 600; }
.markdown-content :deep(tr:nth-child(even)) { background: #fafbfc; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { padding-left: 2em; margin: 0.5em 0; }
.markdown-content :deep(li) { margin: 0.3em 0; }
.markdown-content :deep(code) { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.88em; color: #d63384; }
.markdown-content :deep(pre) { background: #f6f8fa; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; overflow-x: auto; margin: 1em 0; }
.markdown-content :deep(pre code) { background: none; padding: 0; font-size: 0.85em; color: #1e293b; line-height: 1.5; }
.markdown-content :deep(blockquote) { margin: 1em 0; padding: 8px 16px; border-left: 4px solid #4f46e5; background: #f8fafc; color: #64748b; }

.cursor-blink { display: inline; animation: blink 1s step-end infinite; color: #4f46e5; font-size: 1.1rem; }
.generating-status { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 40px 0; color: #94a3b8; font-size: 0.9rem; }
.done-banner { text-align: center; padding: 12px; color: #16a34a; font-size: 0.9rem; font-weight: 500; border-top: 1px solid #e2e8f0; margin-top: 12px; }
.edit-area { display: flex; flex-direction: column; gap: 8px; }
.edit-hint { font-size: 0.75rem; color: #94a3b8; }
.pref-hint { margin-top: 6px; padding: 6px 10px; background: #fef3c7; border-radius: 4px; font-size: 0.78rem; color: #92400e; }

.prompt-hint { font-size: 0.8rem; color: #94a3b8; background: #f8fafc; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px; }
.prompt-body { max-height: 60vh; overflow-y: auto; padding: 16px; margin: 0; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 0.82rem; line-height: 1.6; color: #334155; white-space: pre-wrap; word-wrap: break-word; background: #f8fafc; border-radius: 6px; }
@keyframes blink { 50% { opacity: 0; } }

/* 多选偏好 */
.pref-checkbox-list { display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 12px; }
.pref-checkbox-item { display: flex; align-items: center; gap: 6px; padding: 4px 0; cursor: pointer; font-size: 0.85rem; }
.pref-checkbox-item input[type="checkbox"] { cursor: pointer; }
.pref-checkbox-label { color: #1e293b; }
.default-badge-sm { font-size: 0.7rem; color: #d97706; }
.pref-checkbox-notes { font-size: 0.78rem; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pref-empty { font-size: 0.8rem; color: #94a3b8; padding: 8px 0; text-align: center; }

/* 高级设置折叠面板 */
.advanced-section { margin-bottom: 16px; border: 1px solid #e2e8f0; border-radius: 8px; }
.advanced-section :deep(.el-collapse-item__header) { padding: 0 12px; font-size: 0.85rem; font-weight: 500; }
.advanced-section :deep(.el-collapse-item__content) { padding: 12px; }
.advanced-row { display: flex; gap: 24px; flex-wrap: wrap; }
.advanced-item { flex: 1; min-width: 200px; }
.advanced-item :deep(.el-switch) { margin-bottom: 4px; }
.advanced-desc { font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }
.model-chain-hint { margin-top: 12px; padding-top: 10px; border-top: 1px solid #f1f5f9; font-size: 0.8rem; color: #64748b; display: flex; align-items: center; gap: 8px; }

/* 阶段指示器 */
.phase-indicator { display: flex; align-items: center; gap: 8px; padding: 10px 20px; background: #eef2ff; color: #4f46e5; font-size: 0.85rem; font-weight: 500; border-bottom: 1px solid #e2e8f0; }
.spinner-small { width: 14px; height: 14px; border: 2px solid #c7d2fe; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
/* 验证/修正状态条（不混入正文） */
.status-bar { display: flex; align-items: center; gap: 8px; padding: 6px 20px; background: #fffbeb; color: #92400e; font-size: 0.82rem; border-bottom: 1px solid #fde68a; }

/* 质量验证结果卡片 */
.verify-card { margin: 0 20px; padding: 0; border: 1px solid #dbeafe; border-radius: 8px; background: #f0f7ff; overflow: hidden; }
.verify-card :deep(.el-collapse-item__header) { padding: 0 16px; font-size: 0.82rem; font-weight: 500; background: #f0f7ff; }
.verify-card :deep(.el-collapse-item__wrap) { background: #f0f7ff; border-bottom: none; }
.verify-card :deep(.el-collapse-item__content) { padding: 0 16px 12px; }
.verify-card :deep(.el-collapse) { border-top: none; }
.verify-header { display: flex; align-items: center; gap: 8px; padding: 10px 16px; cursor: pointer; user-select: none; }
.verify-header:hover { background: #e8f2ff; }
.verify-icon { font-size: 1.1rem; }
.verify-title { font-weight: 600; font-size: 0.85rem; color: #1e40af; }
.verify-score { margin-left: auto; padding: 2px 10px; border-radius: 12px; font-weight: 700; font-size: 0.85rem; }
.score-good { background: #dcfce7; color: #16a34a; }
.score-ok { background: #fef3c7; color: #d97706; }
.score-bad { background: #fee2e2; color: #dc2626; }
.collapse-icon { font-size: 0.9rem; color: #94a3b8; transition: transform 0.2s; }
.collapse-icon.rotated { transform: rotate(180deg); }
.verify-issue-item { font-size: 0.82rem; color: #334155; padding: 3px 0; display: flex; align-items: flex-start; gap: 6px; }
.issue-severity { display: inline-block; padding: 0 5px; border-radius: 3px; font-size: 0.7rem; font-weight: 500; white-space: nowrap; flex-shrink: 0; }
.sev-critical { background: #fee2e2; color: #dc2626; }
.sev-normal { background: #fef3c7; color: #d97706; }
.sev-minor { background: #e0f2fe; color: #0284c7; }
.verify-suggestion-item { font-size: 0.82rem; color: #475569; padding: 2px 0; }
.verify-no-issues { font-size: 0.82rem; color: #16a34a; padding: 4px 0; }
</style>