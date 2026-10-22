import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import {
  Check,
  KeyRound,
  ShieldCheck,
  Cpu,
  Eye,
  EyeOff,
  Plus,
  ArrowRight,
  Unplug,
} from "lucide-react";
import {
  capabilitiesOptions,
  connectionsOptions,
  commands,
} from "@/lib/business-api";
import { Button } from "@/components/ui/button";
import { ErrorNotice, useCommand } from "@/components/shared/business-ui";
import { PageHeader, EmptyState } from "@/components/shared/page-layout";

export function useAIAccess() {
  const { data: capabilities } = useSuspenseQuery(capabilitiesOptions);
  const { data: connections } = useSuspenseQuery(connectionsOptions());
  return {
    capabilities,
    connections: connections.items.filter((connection) => connection.enabled),
  };
}

export function AIChoice({
  value,
  onChange,
  disabled = false,
  retry = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  retry?: boolean;
}): React.JSX.Element {
  const { connections } = useAIAccess();
  return (
    <div className="ai-choice">
      <label htmlFor="ai-connection">Nguồn AI</label>
      <select
        id="ai-connection"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">
          {retry ? "Giữ kết nối hiện tại" : "Chọn model đã lưu API key"}
        </option>
        {connections.map((connection) => (
          <option key={connection.id} value={connection.id}>
            {connection.name} · {connection.provider} / {connection.model}
          </option>
        ))}
      </select>
      {!connections.length && (
        <p role="status" className="field-hint">
          Chưa có model được kết nối. Thêm API key để bắt đầu dùng AI.
        </p>
      )}
      <Link className="text-link" to="/ai-settings">
        Cài đặt AI <ArrowRight size={14} aria-hidden="true" />
      </Link>
    </div>
  );
}

export function AISettings(): React.JSX.Element {
  const { data: capabilities } = useSuspenseQuery(capabilitiesOptions);
  const [offset, setOffset] = useState(0);
  const { data: connections } = useSuspenseQuery(connectionsOptions(offset));
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [showKey, setShowKey] = useState(false);
  const discover = useCommand(
    () => commands.discoverModels(provider, apiKey),
    (result) => {
      setModels(result.models);
      setModel(result.models[0] || "");
      setNotice(
        result.models.length
          ? `Đã tìm thấy ${result.models.length} model. Chọn model để lưu kết nối.`
          : "Không tìm thấy model phù hợp.",
      );
    },
  );
  const save = useCommand(
    () =>
      commands.createConnection({
        name: name.trim(),
        provider,
        api_key: apiKey,
        model,
      }),
    () => {
      setApiKey("");
      setModels([]);
      setModel("");
      setName("");
      setShowKey(false);
      setNotice(
        "Đã lưu kết nối. Bạn có thể chọn model này khi bắt đầu hoặc thử lại workflow.",
      );
    },
  );
  const disable = useCommand((id: string) => commands.disableConnection(id));
  const pending = discover.isPending || save.isPending;
  function resetModels(): void {
    setModels([]);
    setModel("");
    setNotice("");
    discover.reset();
    save.reset();
  }
  return (
    <>
      <PageHeader
        eyebrow="CẤU HÌNH KHÔNG GIAN LÀM VIỆC"
        title="Cài đặt AI"
        description="Kết nối model của bạn. Nhập key một lần, sẵn sàng cho mọi workflow."
        action={
          <span className="secure-label">
            <ShieldCheck size={16} /> Key được mã hóa
          </span>
        }
      />
      <div className="settings-layout">
        <section className="panel settings-editor">
          <div className="panel-heading">
            <div className="heading-with-icon">
              <span className="surface-icon">
                <Plus size={20} />
              </span>
              <div>
                <h2>Thêm kết nối AI</h2>
                <p>Một kết nối cho mỗi model bạn muốn sử dụng.</p>
              </div>
            </div>
          </div>
          {!capabilities.key_storage_available && (
            <p className="error-notice" role="alert">
              Dịch vụ lưu key chưa sẵn sàng. Vui lòng kiểm tra cấu hình máy chủ.
            </p>
          )}
          <form
            className="connection-form"
            aria-busy={pending}
            onSubmit={(event) => {
              event.preventDefault();
              if (model && name.trim() && !pending) save.mutate(undefined);
            }}
          >
            <fieldset disabled={pending || !capabilities.key_storage_available}>
              <section className="setup-section">
                <div className="setup-heading">
                  <span className="setup-number">1</span>
                  <div>
                    <h3>Thông tin kết nối</h3>
                    <p>Đặt tên để dễ chọn đúng model khi chạy.</p>
                  </div>
                </div>
                <div className="form-grid">
                  <div className="field">
                    <label htmlFor="connection-name">Tên kết nối</label>
                    <input
                      id="connection-name"
                      required
                      maxLength={100}
                      placeholder="Ví dụ: Gemini cho đội Dev"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="connection-provider">Nhà cung cấp</label>
                    <select
                      id="connection-provider"
                      value={provider}
                      onChange={(event) => {
                        setProvider(event.target.value);
                        setApiKey("");
                        setShowKey(false);
                        resetModels();
                      }}
                    >
                      <option value="openai">OpenAI</option>
                      <option value="gemini">Gemini</option>
                      <option value="deepseek">DeepSeek</option>
                    </select>
                  </div>
                </div>
              </section>
              <section className="setup-section">
                <div className="setup-heading">
                  <span
                    className={`setup-number ${models.length ? "setup-done" : ""}`}
                  >
                    {models.length ? <Check size={16} /> : "2"}
                  </span>
                  <div>
                    <h3>Xác thực API key</h3>
                    <p>Nhập key từ tài khoản API của nhà cung cấp.</p>
                  </div>
                </div>
                <label htmlFor="connection-key">API key</label>
                <div className="secret-input">
                  <KeyRound size={16} aria-hidden="true" />
                  <input
                    id="connection-key"
                    type={showKey ? "text" : "password"}
                    autoComplete="off"
                    spellCheck={false}
                    required
                    minLength={8}
                    maxLength={512}
                    placeholder="Dán API key của bạn"
                    aria-describedby="key-hint"
                    value={apiKey}
                    onChange={(event) => {
                      setApiKey(event.target.value.trim());
                      resetModels();
                    }}
                  />
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={showKey ? "Ẩn API key" : "Hiện API key"}
                    aria-pressed={showKey}
                    onClick={() => setShowKey(!showKey)}
                  >
                    {showKey ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
                <p id="key-hint" className="field-hint">
                  Key được lưu mã hóa, không hiển thị lại sau khi lưu.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  disabled={apiKey.length < 8}
                  onClick={() => discover.mutate(undefined)}
                >
                  <Cpu size={16} />
                  {discover.isPending
                    ? "Đang kiểm tra…"
                    : "Kiểm tra key và lấy model"}
                </Button>
              </section>
              <section className="setup-section">
                <div className="setup-heading">
                  <span className="setup-number">3</span>
                  <div>
                    <h3>Chọn model</h3>
                    <p>Chọn model phù hợp với công việc của đội AI.</p>
                  </div>
                </div>
                <label htmlFor="connection-model">Model</label>
                <select
                  id="connection-model"
                  required
                  disabled={!models.length}
                  value={model}
                  aria-describedby="model-hint"
                  onChange={(event) => setModel(event.target.value)}
                >
                  <option value="">Kiểm tra key để lấy danh sách model</option>
                  {models.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
                <p className="field-hint" id="model-hint">
                  Danh sách model không đảm bảo còn quota hoặc hỗ trợ mọi tác
                  vụ. Quyền gọi được xác minh khi thực thi.
                </p>
              </section>
              <div className="form-footer">
                <span>
                  <ShieldCheck size={15} /> Chỉ tài khoản của bạn truy cập
                </span>
                <Button type="submit" disabled={!model || !name.trim()}>
                  {save.isPending ? "Đang lưu…" : "Lưu kết nối"}
                  <ArrowRight size={16} />
                </Button>
              </div>
            </fieldset>
            <div className="form-feedback">
              <ErrorNotice error={discover.error || save.error} />
              {notice && (
                <p role="status" className="inline-feedback">
                  {notice}
                </p>
              )}
            </div>
          </form>
        </section>
        <aside className="settings-guide">
          <span className="surface-icon">
            <KeyRound size={22} />
          </span>
          <h2>
            Model của bạn.
            <br />
            Quyền kiểm soát của bạn.
          </h2>
          <p>
            Kết nối một lần, chọn lại trong các bước BA và Dev. Bạn có thể
            chuyển model khi cần.
          </p>
          <div className="guide-point">
            <ShieldCheck size={18} />
            <div>
              <strong>Lưu key an toàn</strong>
              <p>Key được mã hóa và gắn với tài khoản PM của bạn.</p>
            </div>
          </div>
          <div className="guide-point">
            <Cpu size={18} />
            <div>
              <strong>Quota từ nhà cung cấp</strong>
              <p>
                Phí API được tính trên tài khoản của bạn. Gói chat không tự cấp
                quota API.
              </p>
            </div>
          </div>
          <div className="guide-point">
            <Unplug size={18} />
            <div>
              <strong>Chủ động ngắt kết nối</strong>
              <p>
                Tắt kết nối để xóa key đã lưu. Lịch sử workflow vẫn được giữ.
              </p>
            </div>
          </div>
        </aside>
      </div>
      <section
        className="saved-connections"
        aria-labelledby="saved-connections-title"
      >
        <div className="section-heading">
          <div>
            <h2 id="saved-connections-title">Kết nối đã lưu</h2>
            <p>Các model sẵn sàng để lựa chọn trong workflow.</p>
          </div>
          <span className="count-badge">
            {connections.items.length} trên trang
          </span>
        </div>
        <ErrorNotice error={disable.error} />
        {!connections.items.length ? (
          <div className="panel">
            <EmptyState
              title="Chưa có kết nối AI"
              description="Thêm key và chọn model ở form phía trên để bắt đầu."
            />
          </div>
        ) : (
          <div className="connection-cards">
            {connections.items.map((connection) => (
              <article className="panel connection-card" key={connection.id}>
                <div className="connection-card-top">
                  <span
                    className={`provider-mark provider-${connection.provider}`}
                    aria-hidden="true"
                  >
                    {connection.provider.slice(0, 1).toUpperCase()}
                  </span>
                  <span
                    className={`status-badge ${connection.enabled ? "status-success" : "status-neutral"}`}
                  >
                    {connection.enabled ? "Đang bật" : "Đã tắt"}
                  </span>
                </div>
                <h3>{connection.name}</h3>
                <p className="connection-model">
                  {connection.provider} / {connection.model} ·{" "}
                  {connection.enabled ? "Đang bật" : "Đã tắt"}
                </p>
                <div className="connection-card-footer">
                  <span>
                    <ShieldCheck size={14} />{" "}
                    {connection.enabled ? "Key đã lưu" : "Key đã xóa"}
                  </span>
                  {connection.enabled && (
                    <AlertDialog.Root>
                      <AlertDialog.Trigger asChild>
                        <Button variant="ghost" disabled={disable.isPending}>
                          Tắt kết nối
                        </Button>
                      </AlertDialog.Trigger>
                      <AlertDialog.Portal>
                        <AlertDialog.Overlay className="dialog-overlay" />
                        <AlertDialog.Content className="dialog-content">
                          <AlertDialog.Title>
                            Tắt kết nối {connection.name}?
                          </AlertDialog.Title>
                          <AlertDialog.Description>
                            Key đã lưu sẽ bị xóa. Các lần gọi đang chạy có thể
                            hoàn tất; lịch sử workflow được giữ nguyên.
                          </AlertDialog.Description>
                          <div className="actions">
                            <AlertDialog.Cancel asChild>
                              <Button variant="outline">Giữ kết nối</Button>
                            </AlertDialog.Cancel>
                            <AlertDialog.Action asChild>
                              <Button
                                variant="danger"
                                onClick={() => disable.mutate(connection.id)}
                              >
                                Xác nhận tắt
                              </Button>
                            </AlertDialog.Action>
                          </div>
                        </AlertDialog.Content>
                      </AlertDialog.Portal>
                    </AlertDialog.Root>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
        {(offset > 0 || connections.items.length >= 100) && (
          <div className="pagination">
            <Button
              variant="outline"
              disabled={offset === 0}
              onClick={() => setOffset(offset - 100)}
            >
              Trang trước
            </Button>
            <span>Trang {offset / 100 + 1}</span>
            <Button
              variant="outline"
              disabled={connections.items.length < 100}
              onClick={() => setOffset(offset + 100)}
            >
              Trang sau
            </Button>
          </div>
        )}
      </section>
    </>
  );
}
