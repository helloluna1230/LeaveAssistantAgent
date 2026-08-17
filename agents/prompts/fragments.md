# Prompt fragments (few-shot / reusable snippets)

Reusable phrasing the agent can draw on. Keep behavior in the system instructions
(`agents/instructions/`); these are optional exemplars for tuning.

## Refusal (cross-user / spoofing)
> 我只能查询你本人有权限访问的休假信息，无法提供其他员工的假期余额或休假记录。

## Balance answer template
> 员工 {employee}（数据截至 {as_of_date}，来自模拟 HR MCP 服务）：{leave_type} 总额 {entitled} 天，
> 已用 {used} 天，剩余 {remaining} 天，其中 {expiring} 天将于 {expiration_date} 过期。

## Policy answer template (with citation)
> 根据《员工休假政策手册 · {section}》：{answer}。（来源：hr-leave-policies）

## Cannot confirm (KB no answer)
> 我在现有休假政策中没有找到关于「{topic}」的明确规定，无法确认。建议咨询 HR。

## Plan summary template
> 方案「{plan_name}」：请 {leave_days_used} 天假，可连休约 {consecutive_days_off} 天。{reason}
> 提醒：以上仅为规划建议，正式申请仍需遵循 HR 审批流程。

## Write confirmation
> 我已为你生成休假预览（{leave_type} {start_date}~{end_date}，共 {days} 天，剩余将变为 {remaining_after} 天）。
> 这不会真正提交申请。需要我继续吗？请回复「确认」。
