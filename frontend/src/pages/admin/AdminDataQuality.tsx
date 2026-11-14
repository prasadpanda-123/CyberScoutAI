import { useEffect, useState } from "react"
import { CheckCircle2, XCircle, AlertTriangle, RefreshCw } from "lucide-react"
import { adminApi } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/toast"
import { Skeleton } from "@/components/ui/skeleton"

export function AdminDataQuality() {
  const { toast } = useToast()
  const [quarantine, setQuarantine] = useState<any[]>([])
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const res = await adminApi.dataQuality()
      if (res) {
        setQuarantine(res.quarantine || [])
        setMetrics(res.metrics)
      }
    } catch (err) {
      console.error(err)
      setLoadError("Could not load data-quality records. Check your connection and try again.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleAction = async (
    id: string,
    action: "approve" | "reject",
    recordType?: "Production Opportunity" | "Staged Candidate"
  ) => {
    if (!id || actingId) return
    setActingId(id)
    try {
      const response = await adminApi.quarantineAction({ item_id: id, action, record_type: recordType })
      if (response?.status !== "success") {
        throw new Error(response?.error || "The server did not confirm the review action.")
      }
      await loadData()
      toast({
        title: action === "approve" ? "Candidate approved" : "Candidate rejected",
        description: "The review action was saved.",
        variant: action === "approve" ? "success" : "default",
      })
    } catch (err: any) {
      toast({
        title: "Action Failed",
        description: err.message || "Failed to process candidate.",
        variant: "destructive",
      })
    } finally {
      setActingId(null)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-amber-500" /> Data Quality & Quarantine Console
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Audit candidate opportunities flagged for ambiguous pricing, potential fees, or missing verification metadata.
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={loadData} className="text-xs">
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Refresh List
        </Button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-t-2 border-t-amber-500">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
              In Quarantine
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono text-amber-600">
              {metrics?.quarantined ?? "—"}
            </div>
            <p className="text-[11px] text-muted-foreground mt-0.5">Records awaiting review</p>
          </CardContent>
        </Card>

        <Card className="border-t-2 border-t-emerald-500">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
              Total Opportunities
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono text-foreground">
              {metrics?.total ?? "—"}
            </div>
            <p className="text-[11px] text-muted-foreground mt-0.5">Opportunities in the catalog</p>
          </CardContent>
        </Card>

        <Card className="border-t-2 border-t-cyber-blue">
          <CardHeader className="pb-1">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
              Missing Critical Fields
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono text-foreground">
              {metrics?.missing_critical ?? "—"}
            </div>
            <p className="text-[11px] text-muted-foreground mt-0.5">Records missing required details</p>
          </CardContent>
        </Card>
      </div>

      {/* Quarantine Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Flagged Candidates Awaiting Human Review</CardTitle>
        </CardHeader>
        <CardContent>
          {loadError ? (
            <div role="alert" className="space-y-3 py-10 text-center">
              <p className="text-sm text-destructive">{loadError}</p>
              <Button variant="outline" size="sm" onClick={loadData}>Try again</Button>
            </div>
          ) : loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : quarantine.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground space-y-2">
              <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto opacity-80" />
              <h4 className="font-semibold text-foreground text-sm">No candidates awaiting review</h4>
              <p className="text-xs max-w-sm mx-auto">
                There are no quarantined records to review right now.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-muted/50 text-muted-foreground font-semibold uppercase text-[10px] tracking-wider border-b">
                  <tr>
                    <th className="p-3">Candidate Title</th>
                    <th className="p-3">Source Engine</th>
                    <th className="p-3">Quarantine Reason</th>
                    <th className="p-3">Detected Pricing Text</th>
                    <th className="p-3 text-right">Review Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {quarantine.map((item, idx) => (
                    <tr key={item.id || idx} className="hover:bg-muted/20 transition-colors">
                      <td className="p-3 font-semibold text-foreground max-w-xs truncate">
                        {item.title || "Untitled Opportunity"}
                        <span className="block text-[10px] text-muted-foreground font-normal">
                          {item.organization || "Unknown"}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-muted-foreground">{item.source_id || "Unknown source"}</td>
                      <td className="p-3">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
                          {item.quarantine_reason || "Unverified Fee Clause"}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-[11px] text-muted-foreground max-w-xs truncate">
                        {item.pricing_evidence || "Not provided by source"}
                      </td>
                      <td className="p-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <Button
                            size="sm"
                            onClick={() => handleAction(String(item.id), "approve", item.type)}
                            disabled={actingId === String(item.id)}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] h-7 px-2"
                          >
                            <CheckCircle2 className="h-3 w-3 mr-1" /> Approve Free
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleAction(String(item.id), "reject", item.type)}
                            disabled={actingId === String(item.id)}
                            className="text-[11px] h-7 px-2"
                          >
                            <XCircle className="h-3 w-3 mr-1" /> Reject
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

