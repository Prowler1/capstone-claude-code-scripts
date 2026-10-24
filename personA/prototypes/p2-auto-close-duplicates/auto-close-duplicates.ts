#!/usr/bin/env bun

declare global {
  interface ImportMeta { main: boolean }
  var process: {
    env: Record<string, string | undefined>;
  };
}

interface GitHubIssue {
  number: number;
  title: string;
  user: { id: number };
  created_at: string;
}

interface GitHubComment {
  id: number;
  body: string;
  created_at: string;
  user: { type: string; id: number };
}

interface GitHubReaction {
  user: { id: number };
  content: string;
}

async function githubRequest<T>(endpoint: string, token: string, method: string = 'GET', body?: any): Promise<T> {
  const response = await fetch(`https://api.github.com${endpoint}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "auto-close-duplicates-script",
      ...(body && { "Content-Type": "application/json" }),
    },
    ...(body && { body: JSON.stringify(body) }),
  });

  if (!response.ok) {
    throw new Error(
      `GitHub API request failed: ${response.status} ${response.statusText}`
    );
  }

  return response.json();
}

function extractDuplicateIssueNumber(commentBody: string): number | null {
  // Try to match #123 format first
  let match = commentBody.match(/#(\d+)/);
  if (match) {
    return parseInt(match[1], 10);
  }
  
  // Try to match GitHub issue URL format: https://github.com/owner/repo/issues/123
  match = commentBody.match(/github\.com\/[^\/]+\/[^\/]+\/issues\/(\d+)/);
  if (match) {
    return parseInt(match[1], 10);
  }
  
  return null;
}


async function closeIssueAsDuplicate(
  owner: string,
  repo: string,
  issueNumber: number,
  duplicateOfNumber: number,
  token: string
): Promise<void> {
  await githubRequest(
    `/repos/${owner}/${repo}/issues/${issueNumber}`,
    token,
    'PATCH',
    {
      state: 'closed',
      state_reason: 'duplicate',
      labels: ['duplicate']
    }
  );

  await githubRequest(
    `/repos/${owner}/${repo}/issues/${issueNumber}/comments`,
    token,
    'POST',
    {
      body: `This issue has been automatically closed as a duplicate of #${duplicateOfNumber}.

If this is incorrect, please re-open this issue or create a new one.

🤖 Generated with [Claude Code](https://claude.ai/code)`
    }
  );

}

const DAY_MS = 24 * 60 * 60 * 1000;

type Verdict =
  | { kind: "skip"; reason: string }
  | { kind: "close"; duplicateOf: number };

export function isOldEnough(createdAt: string, cutoff: Date): boolean {
  return new Date(createdAt) <= cutoff;
}

export function isDupeDetectionComment(comment: GitHubComment): boolean {
  return (
    comment.body.includes("Found") &&
    comment.body.includes("possible duplicate") &&
    comment.user.type === "Bot"
  );
}

export function lastDupeCommentOf(
  comments: GitHubComment[]
): GitHubComment | undefined {
  return comments.filter(isDupeDetectionComment).at(-1);
}

export function hasActivityAfter(
  comments: GitHubComment[],
  comment: GitHubComment
): boolean {
  const at = new Date(comment.created_at);

  return comments.some(each => new Date(each.created_at) > at);
}

export function hasAuthorDisagreed(
  issue: GitHubIssue,
  reactions: GitHubReaction[]
): boolean {
  return reactions.some(
    reaction => reaction.user.id === issue.user.id && reaction.content === "-1"
  );
}

/** Decides from the comments alone; reactions are only fetched on `undefined`. */
export function commentVerdictOf(
  comments: GitHubComment[],
  cutoff: Date
): { kind: "skip"; reason: string } | GitHubComment {
  const last = lastDupeCommentOf(comments);

  if (!last) return { kind: "skip", reason: "no duplicate comments found" };
  if (new Date(last.created_at) > cutoff)
    return { kind: "skip", reason: "duplicate comment is too recent" };
  if (hasActivityAfter(comments, last))
    return { kind: "skip", reason: "has activity after duplicate comment" };

  return last;
}

export function closeVerdictOf(
  issue: GitHubIssue,
  dupeComment: GitHubComment,
  reactions: GitHubReaction[]
): Verdict {
  if (hasAuthorDisagreed(issue, reactions))
    return { kind: "skip", reason: "author disagreed with duplicate detection" };

  const duplicateOf = extractDuplicateIssueNumber(dupeComment.body);

  return duplicateOf
    ? { kind: "close", duplicateOf }
    : { kind: "skip", reason: "could not extract duplicate issue number" };
}

async function fetchOldOpenIssues(
  owner: string,
  repo: string,
  token: string,
  cutoff: Date
): Promise<GitHubIssue[]> {
  const issues: GitHubIssue[] = [];

  for (let page = 1; page <= 20; page++) {
    const pageIssues: GitHubIssue[] = await githubRequest(
      `/repos/${owner}/${repo}/issues?state=open&per_page=100&page=${page}`,
      token
    );

    if (pageIssues.length === 0) break;
    issues.push(...pageIssues.filter(issue => isOldEnough(issue.created_at, cutoff)));
  }

  return issues;
}

async function autoCloseDuplicates(): Promise<void> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    throw new Error("GITHUB_TOKEN environment variable is required");
  }

  const owner = process.env.GITHUB_REPOSITORY_OWNER || "anthropics";
  const repo = process.env.GITHUB_REPOSITORY_NAME || "claude-code";
  const cutoff = new Date(Date.now() - 3 * DAY_MS);

  const issues = await fetchOldOpenIssues(owner, repo, token, cutoff);
  let candidateCount = 0;

  for (const issue of issues) {
    const comments: GitHubComment[] = await githubRequest(
      `/repos/${owner}/${repo}/issues/${issue.number}/comments`,
      token
    );

    const byComments = commentVerdictOf(comments, cutoff);
    if ("kind" in byComments) {
      console.log(`[DEBUG] Issue #${issue.number} - ${byComments.reason}, skipping`);
      continue;
    }

    const reactions: GitHubReaction[] = await githubRequest(
      `/repos/${owner}/${repo}/issues/comments/${byComments.id}/reactions`,
      token
    );

    const verdict = closeVerdictOf(issue, byComments, reactions);
    if (verdict.kind === "skip") {
      console.log(`[DEBUG] Issue #${issue.number} - ${verdict.reason}, skipping`);
      continue;
    }

    candidateCount++;
    try {
      await closeIssueAsDuplicate(owner, repo, issue.number, verdict.duplicateOf, token);
      console.log(`[SUCCESS] Closed #${issue.number} as duplicate of #${verdict.duplicateOf}`);
    } catch (error) {
      console.error(`[ERROR] Failed to close issue #${issue.number} as duplicate: ${error}`);
    }
  }

  console.log(
    `[DEBUG] Script completed. Processed ${issues.length} issues, found ${candidateCount} candidates for auto-close`
  );
}

if (import.meta.main) autoCloseDuplicates().catch(console.error);
