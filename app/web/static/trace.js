/**
 * Trace 可视化渲染器
 *
 * 把 Agent Trace 的 JSON 数据渲染成步骤化的 HTML：
 *   用户输入 → [第1轮] 工具调用 → [第2轮] 工具调用 → 最终回答
 *
 * 在 dashboard.html（弹窗）和 case_detail.html（内嵌）中共享使用。
 */

/**
 * 渲染完整的 Trace HTML
 * @param {Object} trace - trace.to_dict() 返回的对象
 * @returns {string} HTML 字符串
 */
function renderTrace(trace) {
    if (!trace || !trace.steps) {
        return '<p class="trace-empty">暂无 Trace 数据</p>';
    }

    let html = '<div class="trace-flow">';

    // ---- 用户输入 ----
    html += `
        <div class="trace-step trace-step-user">
            <div class="trace-step-icon">👤</div>
            <div class="trace-step-content">
                <div class="trace-step-title">用户输入</div>
                <div class="trace-step-body">${escapeHtml(trace.user_input)}</div>
            </div>
        </div>
    `;

    // ---- 每轮工具调用 ----
    trace.steps.forEach(function(step) {
        var isBlocked = step.tool_result && step.tool_result.blocked;
        var isError = step.tool_result && step.tool_result.error && !isBlocked;
        var stepClass = isBlocked ? 'trace-step-blocked' : (isError ? 'trace-step-error' : 'trace-step-tool');
        var icon = isBlocked ? '🚫' : (isError ? '⚠️' : '🔧');
        var statusLabel = isBlocked ? ' (权限拦截)' : (isError ? ' (执行错误)' : '');

        html += `
            <div class="trace-arrow">↓</div>
            <div class="trace-step ${stepClass}">
                <div class="trace-step-icon">${icon}</div>
                <div class="trace-step-content">
                    <div class="trace-step-title">
                        第 ${step.round} 轮 · ${escapeHtml(step.tool_name)}${statusLabel}
                    </div>
                    <div class="trace-step-body">
                        <div class="trace-section">
                            <span class="trace-label">参数</span>
                            <pre class="trace-code">${escapeHtml(JSON.stringify(step.tool_arguments, null, 2))}</pre>
                        </div>
                        <div class="trace-section">
                            <span class="trace-label">结果</span>
                            <pre class="trace-code">${escapeHtml(JSON.stringify(step.tool_result, null, 2))}</pre>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });

    // ---- 最终回答 ----
    if (trace.final_answer) {
        var icon = trace.success ? '✅' : '❌';
        var stepClass = trace.success ? 'trace-step-final' : 'trace-step-error';
        var label = trace.success ? '最终回答 (成功)' : '最终回答 (失败)';
        html += `
            <div class="trace-arrow">↓</div>
            <div class="trace-step ${stepClass}">
                <div class="trace-step-icon">${icon}</div>
                <div class="trace-step-content">
                    <div class="trace-step-title">${label}</div>
                    <div class="trace-step-body trace-answer-box">${escapeHtml(trace.final_answer)}</div>
                </div>
            </div>
        `;
    }

    html += '</div>';

    // ---- 统计信息 ----
    var numToolCalls = trace.num_tool_calls || trace.steps.length;
    html += `
        <div class="trace-stats">
            <span class="trace-stat-item">LLM 调用: <strong>${trace.num_llm_calls}</strong> 次</span>
            <span class="trace-stat-item">工具调用: <strong>${numToolCalls}</strong> 次</span>
            <span class="trace-stat-item">总耗时: <strong>${trace.total_time}</strong>s</span>
            <span class="trace-stat-item">总 Token: <strong>${trace.total_tokens}</strong></span>
        </div>
    `;

    return html;
}

/**
 * HTML 转义，防止用户输入的内容破坏 HTML 结构
 */
function escapeHtml(text) {
    if (text == null) return '';
    var div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}
