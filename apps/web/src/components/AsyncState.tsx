import { Button, MessageBar, MessageBarBody, Spinner } from "@fluentui/react-components";

interface AsyncStateProps {
  title: string;
  detail?: string;
  kind?: "loading" | "empty" | "error" | "forbidden";
  retry?: () => void;
}

export function AsyncState({
  title,
  detail,
  kind = "empty",
  retry,
}: AsyncStateProps) {
  if (kind === "loading") {
    return (
      <section className="state-panel" role="status" aria-live="polite">
        <Spinner label={title} />
      </section>
    );
  }
  return (
    <section className="state-panel" role={kind === "error" ? "alert" : "status"}>
      <MessageBar intent={kind === "error" ? "error" : "info"}>
        <MessageBarBody>
          <h2>{title}</h2>
          {detail && <p>{detail}</p>}
          {retry && (
            <Button appearance="primary" onClick={retry}>
              Retry
            </Button>
          )}
        </MessageBarBody>
      </MessageBar>
    </section>
  );
}
