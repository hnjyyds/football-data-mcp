import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ValidationJobActionBar } from "./ValidationJobActionBar";
import type { ValidationJob } from "../../types";

function job(overrides: Partial<ValidationJob> = {}): ValidationJob {
  return {
    job_id: "holdout-1",
    method: "holdout_validation_job_v1",
    status: "failed",
    divisions: ["E0", "SP1"],
    training_seasons: ["2122"],
    validation_seasons: ["2223"],
    progress: {
      total_leagues: 2,
      completed_leagues: 1,
      failed_leagues: 1,
      running_leagues: 0,
      pending_leagues: 0,
      cancelled_leagues: 0,
      processed_leagues: 2,
      progress_ratio: 1,
      success_ratio: 0.5,
    },
    league_results: [],
    events: [],
    ...overrides,
  };
}

function renderActionBar(overrides: Partial<ValidationJob> = {}, actionJobId: string | null = null) {
  const onStart = vi.fn();
  const onQuickStart = vi.fn();
  const onCancel = vi.fn();
  const onRetry = vi.fn();
  const currentJob = job(overrides);

  render(
    <ValidationJobActionBar
      job={currentJob}
      actionJobId={actionJobId}
      statusLabel={currentJob.status === "failed" ? "失败" : currentJob.status === "running" ? "运行中" : "已完成"}
      statusTone={currentJob.status === "failed" ? "bad" : currentJob.status === "running" ? "caution" : "good"}
      startLabel={currentJob.status === "completed" ? "重跑验证" : "继续验证"}
      onQuickStart={onQuickStart}
      onStart={onStart}
      onCancel={onCancel}
      onRetry={onRetry}
    />,
  );

  return { currentJob, onStart, onQuickStart, onCancel, onRetry };
}

describe("ValidationJobActionBar", () => {
  it("lets users retry a failed validation job from unfinished leagues", () => {
    const { onRetry } = renderActionBar();

    expect(screen.getByText("失败")).toBeInTheDocument();
    expect(screen.getByText("已处理 2/2 联赛")).toBeInTheDocument();
    expect(screen.getByText("失败 1 联赛")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    expect(onRetry).toHaveBeenCalledWith("holdout-1");
  });

  it("lets users cancel a running validation job without exposing retry/start actions", () => {
    const { onCancel } = renderActionBar({
      status: "running",
      progress: {
        total_leagues: 3,
        completed_leagues: 1,
        failed_leagues: 0,
        running_leagues: 1,
        pending_leagues: 1,
        processed_leagues: 1,
        progress_ratio: 0.333333,
      },
    });

    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "继续验证" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    expect(onCancel).toHaveBeenCalledWith("holdout-1");
  });

  it("lets users rerun a completed validation job", () => {
    const { onStart } = renderActionBar({
      status: "completed",
      progress: {
        total_leagues: 2,
        completed_leagues: 2,
        failed_leagues: 0,
        running_leagues: 0,
        pending_leagues: 0,
        processed_leagues: 2,
        progress_ratio: 1,
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "重跑验证" }));

    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("lets users start a quick diagnostic without triggering the full validation", () => {
    const { onStart, onQuickStart } = renderActionBar({
      status: "completed",
      progress: {
        total_leagues: 2,
        completed_leagues: 2,
        failed_leagues: 0,
        running_leagues: 0,
        pending_leagues: 0,
        processed_leagues: 2,
        progress_ratio: 1,
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "快速诊断" }));

    expect(onQuickStart).toHaveBeenCalledTimes(1);
    expect(onStart).not.toHaveBeenCalled();
  });

  it("disables the active job action while a queue request is in flight", () => {
    const { onRetry } = renderActionBar({}, "holdout-1");
    const retryButton = screen.getByRole("button", { name: "重试" });

    expect(retryButton).toBeDisabled();
    fireEvent.click(retryButton);

    expect(onRetry).not.toHaveBeenCalled();
  });
});
