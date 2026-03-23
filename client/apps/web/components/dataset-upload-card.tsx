"use client"

import * as React from "react"
import { UploadSimple, Plus, X, CheckCircle } from "@phosphor-icons/react"
import type { SellerClaim } from "@/lib/types"

interface DatasetUploadCardProps {
  datasetName: string
  onDatasetNameChange: (v: string) => void
  datasetReference: string
  onDatasetReferenceChange: (v: string) => void
  reservePrice: string
  onReservePriceChange: (v: string) => void
  claims: SellerClaim[]
  onClaimsChange: (claims: SellerClaim[]) => void
  note: string
  onNoteChange: (v: string) => void
  file?: File | null
  onFileChange: (f: File | null) => void
}

export function DatasetUploadCard({
  datasetName,
  onDatasetNameChange,
  datasetReference,
  onDatasetReferenceChange,
  reservePrice,
  onReservePriceChange,
  claims,
  onClaimsChange,
  note,
  onNoteChange,
  file,
  onFileChange,
}: DatasetUploadCardProps) {
  const [newClaimName, setNewClaimName] = React.useState("")
  const [newClaimValue, setNewClaimValue] = React.useState("")
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null
    onFileChange(f)
  }

  function handleDropZoneClick() {
    fileInputRef.current?.click()
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0] ?? null
    if (f) onFileChange(f)
  }

  function addClaim() {
    if (!newClaimName.trim()) return
    onClaimsChange([...claims, { name: newClaimName.trim(), value: newClaimValue.trim() }])
    setNewClaimName("")
    setNewClaimValue("")
  }

  function removeClaim(i: number) {
    onClaimsChange(claims.filter((_, idx) => idx !== i))
  }

  return (
    <div className="space-y-6">
      {/* Trust boundary notice */}
      <div className="rounded-xl border border-success/30 bg-success/5 px-4 py-3 text-sm text-success">
        Raw dataset rows never leave the enclave before final agreement. Only bounded evaluation metrics are exposed.
      </div>

      {/* Dataset name */}
      <div>
        <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">
          Dataset name <span className="text-red-500">*</span>
        </label>
        <input
          value={datasetName}
          onChange={(e) => onDatasetNameChange(e.target.value)}
          placeholder="e.g. Financial Records Q4 2024"
          className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
        />
      </div>

      {/* Dataset upload or reference */}
      <div>
        <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">Dataset</label>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleFileSelect}
        />
        <div
          onClick={handleDropZoneClick}
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="rounded-xl border border-dashed border-[#d2d2d7] bg-[#f5f5f7] px-4 py-8 text-center hover:border-primary/30 transition-colors cursor-pointer mb-3"
        >
          {file ? (
            <>
              <CheckCircle weight="fill" className="size-8 text-success mx-auto mb-2" />
              <p className="text-sm font-medium text-[#1d1d1f]">{file.name}</p>
              <p className="text-xs text-[#aeaeb2] mt-1">{(file.size / 1024).toFixed(1)} KB — click to replace</p>
            </>
          ) : (
            <>
              <UploadSimple className="size-8 text-[#aeaeb2] mx-auto mb-2" />
              <p className="text-sm text-[#6e6e73]">Drag & drop your CSV or click to upload</p>
              <p className="text-xs text-[#aeaeb2] mt-1">CSV only — sent directly to the enclave over TLS</p>
            </>
          )}
        </div>
        <div className="flex items-center gap-3 mb-3">
          <div className="flex-1 h-px bg-[#e8e8ed]" />
          <span className="text-xs text-[#aeaeb2]">or reference by URL</span>
          <div className="flex-1 h-px bg-[#e8e8ed]" />
        </div>
        <input
          value={datasetReference}
          onChange={(e) => onDatasetReferenceChange(e.target.value)}
          placeholder="s3://bucket/dataset.parquet or IPFS hash"
          className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-2.5 text-sm font-mono text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
        />
      </div>

      {/* Reserve price */}
      <div>
        <label className="text-sm font-medium text-[#1d1d1f] mb-1 block">
          Reserve price <span className="text-red-500">*</span>
        </label>
        <p className="text-xs text-[#aeaeb2] mb-2">
          Your minimum acceptable payment. This remains confidential inside the enclave.
        </p>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6e6e73] text-sm">$</span>
          <input
            type="text"
            value={reservePrice}
            onChange={(e) => onReservePriceChange(e.target.value.replace(/[^\d,.]/g, ""))}
            placeholder="5,000"
            className="w-full rounded-xl border border-[#d2d2d7] bg-white pl-7 pr-4 py-2.5 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
          />
        </div>
      </div>

      {/* Seller claims */}
      <div>
        <label className="text-sm font-medium text-[#1d1d1f] mb-1 block">Seller claims</label>
        <p className="text-xs text-[#aeaeb2] mb-3">
          Verifiable assertions the enclave will check against the dataset.
        </p>
        {claims.length > 0 && (
          <div className="space-y-2 mb-3">
            {claims.map((c, i) => (
              <div key={i} className="flex items-center gap-2 rounded-lg border border-[#e8e8ed] bg-[#f5f5f7] px-3 py-2">
                <span className="flex-1 text-sm text-[#1d1d1f]">{c.name}</span>
                {c.value && <span className="text-sm text-[#6e6e73] font-mono">{String(c.value)}</span>}
                <button onClick={() => removeClaim(i)} className="text-[#aeaeb2] hover:text-red-500 transition-colors">
                  <X className="size-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input
            value={newClaimName}
            onChange={(e) => setNewClaimName(e.target.value)}
            placeholder="Claim (e.g. 10,000+ rows)"
            className="flex-1 rounded-xl border border-[#d2d2d7] bg-white px-3 py-2 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
          />
          <input
            value={newClaimValue}
            onChange={(e) => setNewClaimValue(e.target.value)}
            placeholder="Value (optional)"
            className="w-28 rounded-xl border border-[#d2d2d7] bg-white px-3 py-2 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
          />
          <button
            onClick={addClaim}
            disabled={!newClaimName.trim()}
            className="rounded-xl border border-[#d2d2d7] px-3 py-2 text-[#6e6e73] hover:border-[#aeaeb2] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <Plus className="size-4" />
          </button>
        </div>
      </div>

      {/* Optional note */}
      <div>
        <label className="text-sm font-medium text-[#1d1d1f] mb-2 block">Note (optional)</label>
        <textarea
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
          placeholder="Any additional context for the buyer…"
          rows={3}
          className="w-full rounded-xl border border-[#d2d2d7] bg-white px-4 py-3 text-sm text-[#1d1d1f] placeholder:text-[#aeaeb2] focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all resize-none leading-relaxed"
        />
      </div>
    </div>
  )
}
