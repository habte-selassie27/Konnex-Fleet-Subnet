// PolicyRegistry — miner-facing policy submissions (AGENTS.md §1.2/§1.8).
//
// The browser hashes the selected artifact with Web Crypto and sends that
// SHA-256 with the bytes; the backend re-computes it and rejects a mismatch
// with 422, so a policy can never be registered under the wrong hash.
// The list is loaded from GET /api/v1/policies — no mock rows.
import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, FileUp, Hash, ShieldCheck, Upload } from 'lucide-react'

import { api } from '../../services/api'
import type { PolicyRecord, PolicySubmitPayload } from '../../types'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { StatusBadge } from '../shared/StatusBadge'

const MAX_ARTIFACT_BYTES = 5 * 1024 * 1024

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'data'; rows: PolicyRecord[] }

type SubmitState =
  | { kind: 'idle' }
  | { kind: 'submitting' }
  | { kind: 'success'; policy: PolicyRecord }
  | { kind: 'error'; message: string }

const INPUT_CLASS =
  'w-full rounded-lg border border-line/60 bg-elevated px-2 py-1.5 text-xs text-fg ' +
  'placeholder:text-subtle focus:border-line-strong focus:outline-none ' +
  'focus:ring-2 focus:ring-line-strong/40'

function toBase64(bytes: Uint8Array): string {
  let binary = ''
  const chunkSize = 0x8000
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize))
  }
  return btoa(binary)
}

async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

function shortHash(hash: string): string {
  return hash.length > 16 ? `${hash.slice(0, 16)}…` : hash
}

export function PolicyRegistry() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const [submitState, setSubmitState] = useState<SubmitState>({ kind: 'idle' })
  const [name, setName] = useState('')
  const [author, setAuthor] = useState('')
  const [algorithm, setAlgorithm] = useState('nearest')
  const [file, setFile] = useState<File | null>(null)
  const [fileHash, setFileHash] = useState('')

  const load = useCallback(async () => {
    try {
      const rows = await api.listPolicies()
      setState({ kind: 'data', rows })
    } catch (error: unknown) {
      setState({ kind: 'error', message: error instanceof Error ? error.message : 'Request failed' })
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const onFile = async (selected: File | null) => {
    setFile(selected)
    setFileHash('')
    setSubmitState({ kind: 'idle' })
    if (!selected) return
    if (selected.size > MAX_ARTIFACT_BYTES) {
      setSubmitState({ kind: 'error', message: 'Artifact exceeds the 5 MiB submission limit.' })
      return
    }
    if (!globalThis.crypto?.subtle) {
      setSubmitState({
        kind: 'error',
        message: 'Web Crypto is unavailable — open the dashboard on localhost or HTTPS.',
      })
      return
    }
    setFileHash(await sha256Hex(await selected.arrayBuffer()))
  }

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) {
      setSubmitState({ kind: 'error', message: 'Choose a policy artifact to submit.' })
      return
    }
    if (!name.trim()) {
      setSubmitState({ kind: 'error', message: 'Policy name is required.' })
      return
    }
    try {
      setSubmitState({ kind: 'submitting' })
      const payload: PolicySubmitPayload = {
        name: name.trim(),
        version: '0.1.0',
        author: author.trim(),
        algorithm: algorithm.trim(),
        policy_hash: fileHash,
        artifact_base64: toBase64(new Uint8Array(await file.arrayBuffer())),
      }
      const policy = await api.submitPolicy(payload)
      setSubmitState({ kind: 'success', policy })
      setName('')
      setAuthor('')
      setFile(null)
      setFileHash('')
      await load()
    } catch (error: unknown) {
      setSubmitState({
        kind: 'error',
        message: error instanceof Error ? error.message : 'Submission failed',
      })
    }
  }

  return (
    <section aria-label="Policy registry" className="rounded-xl border border-line/60 bg-panel p-4">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <Hash className="h-3.5 w-3.5" aria-hidden="true" />
        Policies
        {state.kind === 'data' && state.rows.length > 0 && (
          <span className="ml-1 rounded-full bg-line/40 px-2 py-0.5 font-mono text-[10px] text-muted">
            {state.rows.length} verified
          </span>
        )}
      </h2>

      {state.kind === 'loading' && <LoadingSpinner label="Loading submitted policies…" />}

      {state.kind === 'error' && (
        <p className="mt-3 text-xs text-red-400" role="alert">
          Policies unavailable: {state.message}
        </p>
      )}

      {state.kind === 'data' && state.rows.length === 0 && (
        <p className="mt-3 rounded-lg border border-dashed border-line/60 px-3 py-6 text-center text-xs text-subtle">
          No policies submitted yet — upload an artifact below to register one.
        </p>
      )}

      {state.kind === 'data' && state.rows.length > 0 && (
        <div className="mt-3 max-h-56 overflow-auto">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Submitted policies with server-verified SHA-256 hashes</caption>
            <thead className="sticky top-0 bg-panel">
              <tr className="border-b border-line/60 text-subtle">
                <th scope="col" className="pb-2 pr-3 font-medium">Policy</th>
                <th scope="col" className="pb-2 pr-3 font-medium">Algorithm</th>
                <th scope="col" className="pb-2 pr-3 font-medium">SHA-256</th>
                <th scope="col" className="pb-2 pr-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {state.rows.map((row) => (
                <tr key={row.id} className="border-b border-line/30 last:border-0">
                  <td className="py-2 pr-3">
                    <div className="font-medium text-fg">{row.name}</div>
                    <div className="font-mono text-[10px] text-subtle">
                      v{row.version}
                      {row.author ? ` · ${row.author}` : ''}
                      {` · ${row.size_bytes} B`}
                    </div>
                  </td>
                  <td className="py-2 pr-3 font-mono text-fg">{row.algorithm}</td>
                  <td className="py-2 pr-3 font-mono text-[10px] text-muted" title={row.policy_hash}>
                    {shortHash(row.policy_hash)}
                  </td>
                  <td className="py-2">
                    <StatusBadge
                      label={row.status}
                      icon={ShieldCheck}
                      className="bg-emerald-500/15 text-emerald-400"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form className="mt-4 space-y-2 border-t border-line/40 pt-3" onSubmit={onSubmit}>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <label className="text-[10px] uppercase tracking-wide text-subtle">
            Name
            <input
              className={`mt-1 ${INPUT_CLASS}`}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="my-hungarian-v2"
              aria-label="Policy name"
            />
          </label>
          <label className="text-[10px] uppercase tracking-wide text-subtle">
            Author
            <input
              className={`mt-1 ${INPUT_CLASS}`}
              value={author}
              onChange={(event) => setAuthor(event.target.value)}
              placeholder="miner handle"
              aria-label="Policy author"
            />
          </label>
          <label className="text-[10px] uppercase tracking-wide text-subtle">
            Algorithm
            <input
              className={`mt-1 ${INPUT_CLASS}`}
              value={algorithm}
              onChange={(event) => setAlgorithm(event.target.value)}
              placeholder="nearest"
              aria-label="Policy algorithm"
            />
          </label>
        </div>

        <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
          <FileUp className="h-3.5 w-3.5" aria-hidden="true" />
          <input
            type="file"
            className="max-w-[14rem] text-[11px] text-muted file:mr-2 file:rounded-md file:border-0 file:bg-elevated file:px-2 file:py-1 file:text-xs file:text-fg"
            onChange={(event) => void onFile(event.target.files?.[0] ?? null)}
            aria-label="Policy artifact"
          />
        </label>

        {fileHash && (
          <p className="flex items-center gap-1 font-mono text-[10px] text-subtle">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" aria-hidden="true" />
            SHA-256 {shortHash(fileHash)} · {file?.size ?? 0} B
          </p>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitState.kind === 'submitting'}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line/60 bg-elevated px-3 py-1.5 text-xs font-medium text-fg transition-colors hover:border-line-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Upload className="h-3.5 w-3.5" aria-hidden="true" />
            {submitState.kind === 'submitting' ? 'Verifying…' : 'Submit policy'}
          </button>
          {submitState.kind === 'success' && (
            <p className="text-[11px] text-emerald-400" role="status">
              Registered {submitState.policy.name} ({shortHash(submitState.policy.policy_hash)})
              {submitState.policy.duplicate ? ' — already known, same artifact' : ''}
            </p>
          )}
          {submitState.kind === 'error' && (
            <p className="text-[11px] text-red-400" role="alert">
              {submitState.message}
            </p>
          )}
        </div>
      </form>

      <p className="mt-3 text-[10px] leading-relaxed text-subtle">
        The backend re-computes SHA-256 from the uploaded bytes and rejects a mismatch. Limits: 5 MiB
        per artifact; registration does not imply a score.
      </p>
    </section>
  )
}
