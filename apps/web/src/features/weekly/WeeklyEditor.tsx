import { Button, MessageBar, MessageBarBody } from "@fluentui/react-components";
import { useMutation } from "@tanstack/react-query";
import type { ProjectAssistantClient, WeeklyReport } from "@project-assistant/api-client";
import { useEffect, useState } from "react";

export function WeeklyEditor({ client, report, teamId, onChange }: { client: ProjectAssistantClient; report: WeeklyReport; teamId?: string; onChange: (report: WeeklyReport) => void }) {
  const [content, setContent] = useState(JSON.stringify(report.contentJson, null, 2));
  const [parseError, setParseError] = useState("");
  const [publishApproved, setPublishApproved] = useState(false);
  const [conversationId, setConversationId] = useState("");
  const [publicationMessage, setPublicationMessage] = useState("");
  useEffect(() => setContent(JSON.stringify(report.contentJson, null, 2)), [report]);
  const save = useMutation({ mutationFn: (contentJson: Record<string, unknown>) => client.updateWeekly(report.id, teamId, contentJson), onSuccess: onChange });
  const confirm = useMutation({ mutationFn: () => client.confirmWeekly(report.id, teamId), onSuccess: onChange });
  const revise = useMutation({ mutationFn: () => client.createWeeklyRevision(report.id, teamId), onSuccess: onChange });
  const publish = useMutation({ mutationFn: () => client.publishWeekly(report.id, conversationId), onSuccess: (result) => setPublicationMessage(`Published at ${result.publishedAt}.`) });

  function saveContent() {
    setParseError("");
    try {
      const parsed = JSON.parse(content) as unknown;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Report content must be a JSON object.");
      save.mutate(parsed as Record<string, unknown>);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Report content is not valid JSON.");
    }
  }
  const error = save.error ?? confirm.error ?? revise.error ?? publish.error;
  return (
    <div className="weekly-editor">
      <div className="report-meta"><span className="status-chip">{report.status}</span><span>Week {report.weekStart} to {report.weekEnd}</span><span>{report.inputRecordIds.length} evidence records</span><span>Template v{report.templateVersion}</span></div>
      {report.missingContributors.length > 0 && <MessageBar intent="warning"><MessageBarBody>Missing confirmations: {report.missingContributors.join(", ")}</MessageBarBody></MessageBar>}
      <label className="field"><span>Report content</span><textarea aria-label="Report content" rows={18} value={content} onChange={(event) => setContent(event.target.value)} readOnly={report.status === "CONFIRMED"} /><small>Only facts represented in the linked evidence may be retained.</small></label>
      {(parseError || error) && <MessageBar intent="error"><MessageBarBody>{parseError || error?.message}</MessageBarBody></MessageBar>}
      <div className="form-actions">{report.status !== "CONFIRMED" ? <><Button onClick={saveContent} disabled={save.isPending}>Save draft</Button><Button appearance="primary" onClick={() => confirm.mutate()} disabled={confirm.isPending}>Confirm report</Button></> : <Button onClick={() => revise.mutate()} disabled={revise.isPending}>Create revision</Button>}</div>
      <section className="publish-panel" aria-labelledby={`publish-${report.id}`}>
        <div><p className="kicker">EXPLICIT DELIVERY</p><h3 id={`publish-${report.id}`}>Publish to Teams</h3><p>Confirmation and publication are separate. Nothing is sent until you approve this delivery.</p></div>
        <label className="field"><span>Conversation ID</span><input value={conversationId} onChange={(event) => setConversationId(event.target.value)} placeholder="Captured Teams conversation ID" /></label>
        <label className="check-field"><input type="checkbox" checked={publishApproved} onChange={(event) => setPublishApproved(event.target.checked)} /><span>I confirm this report can be published to the selected conversation.</span></label>
        <Button appearance="primary" disabled={!publishApproved || !conversationId || publish.isPending} onClick={() => publish.mutate()}>Publish confirmed report</Button>
        {publicationMessage && <MessageBar intent="success"><MessageBarBody>{publicationMessage}</MessageBarBody></MessageBar>}
      </section>
    </div>
  );
}
