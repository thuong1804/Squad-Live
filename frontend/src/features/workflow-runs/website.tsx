import { useState } from "react";
import { useSuspenseQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api, websiteDownloadUrl } from "@/lib/api-client";
import { pageSchema } from "@/types/contracts";
import type { Run } from "@/types/contracts";
import { shouldPoll } from "@/lib/status";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { DataBoundary } from "@/components/shared/data-boundary";
import { ErrorNotice, Pagination } from "@/components/shared/business-ui";

const versionSchema = z.object({
  id: z.string(),
  revision: z.number(),
  attempt: z.number(),
  created_at: z.string(),
});
const siteSchema = z.object({
  id: z.string(),
  revision: z.number(),
  attempt: z.number(),
  title: z.string(),
  summary: z.string(),
  files: z.array(
    z.object({
      path: z.enum(["index.html", "styles.css", "script.js"]),
      content: z.string(),
    }),
  ),
  notes: z.array(z.string()),
  preview_html: z.string(),
});

function WebsiteVersion({
  run,
  artifactId,
}: {
  run: Run;
  artifactId: string;
}): React.JSX.Element {
  const { data: site } = useSuspenseQuery({
    queryKey: ["website", run.id, artifactId],
    queryFn: ({ signal }) =>
      api.request(
        `/api/v1/workflow-runs/${run.id}/websites/${artifactId}`,
        siteSchema.parse,
        { signal },
      ),
  });
  const [tab, setTab] = useState<"files" | "preview">("files");
  const [file, setFile] = useState("index.html");
  const [mobile, setMobile] = useState(false);
  return (
    <>
      <h3>{site.title}</h3>
      <p>{site.summary}</p>
      <p>
        Bản {site.revision} · Lần {site.attempt}
        {site.revision !== run.revision
          ? " · Bản cũ, không phải kết quả của bản chỉnh sửa hiện tại"
          : ""}
      </p>
      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value as "files" | "preview")}
      >
        <div className="preview-toolbar">
          <TabsList aria-label="Website">
            <TabsTrigger value="files">Danh sách file</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
          </TabsList>
          <a
            className="button button-outline"
            href={websiteDownloadUrl(run.id, artifactId)}
          >
            Tải ZIP
          </a>
        </div>
        <TabsContent value="files">
          <label htmlFor="website-file">File mã nguồn</label>
          <select
            id="website-file"
            value={file}
            onChange={(event) => setFile(event.target.value)}
          >
            {site.files.map((entry) => (
              <option key={entry.path}>{entry.path}</option>
            ))}
          </select>
          <pre className="website-source">
            <code>
              {site.files.find((entry) => entry.path === file)?.content}
            </code>
          </pre>
        </TabsContent>
        <TabsContent value="preview">
          <div className="actions">
            <Button
              variant="outline"
              aria-pressed={mobile}
              onClick={() => setMobile(!mobile)}
            >
              {mobile ? "Xem desktop" : "Xem mobile"}
            </Button>
            <Button variant="outline" onClick={() => setTab("files")}>
              Đóng Preview
            </Button>
          </div>
          <p className="muted">
            Preview chạy cách ly. Kết nối API, gửi form, popup và tài nguyên bên
            ngoài bị chặn. Đây là bản xem để PM kiểm tra, chưa phải kết quả
            Tester.
          </p>
          <div className="website-preview-wrap">
            <iframe
              title="Preview website"
              sandbox="allow-scripts"
              referrerPolicy="no-referrer"
              srcDoc={site.preview_html}
              className={
                mobile ? "website-preview preview-mobile" : "website-preview"
              }
            />
          </div>
        </TabsContent>
      </Tabs>
      {site.notes.length > 0 && (
        <details>
          <summary>Ghi chú của Dev</summary>
          <ul>
            {site.notes.map((note, index) => (
              <li key={index}>{note}</li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

export function WebsiteResults({ run }: { run: Run }): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const { data, error } = useSuspenseQuery({
    queryKey: ["websites", run.id, offset],
    queryFn: ({ signal }) =>
      api.request(
        `/api/v1/workflow-runs/${run.id}/websites?limit=25&offset=${offset}`,
        pageSchema(versionSchema).parse,
        { signal },
      ),
    refetchInterval: shouldPoll(run.status) ? 3000 : false,
  });
  const artifactId = data.items.some((item) => item.id === selected)
    ? selected
    : data.items[0]?.id;
  return (
    <section
      className="panel content-panel website-results"
      id="website-results"
    >
      <h2>Kết quả website</h2>
      <ErrorNotice error={error} />
      {!data.items.length ? (
        <p>
          Dev sẽ tạo file sau khi bạn phê duyệt kế hoạch. Kết quả và Preview sẽ
          xuất hiện tại đây.
        </p>
      ) : (
        <>
          <label htmlFor="website-version">Phiên bản website</label>
          <select
            id="website-version"
            value={artifactId}
            onChange={(event) => setSelected(event.target.value)}
          >
            {data.items.map((item) => (
              <option key={item.id} value={item.id}>
                Bản {item.revision} · Lần {item.attempt}
              </option>
            ))}
          </select>
          <DataBoundary key={artifactId}>
            <WebsiteVersion
              key={artifactId}
              run={run}
              artifactId={artifactId!}
            />
          </DataBoundary>
        </>
      )}
      {(offset > 0 || data.items.length === 25) && (
        <Pagination
          offset={offset}
          count={data.items.length}
          onChange={(value) => {
            setOffset(value);
            setSelected("");
          }}
        />
      )}
    </section>
  );
}
