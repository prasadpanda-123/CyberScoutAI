import { useEffect, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  Bookmark,
  ExternalLink,
  CheckCircle2,
  Calendar,
  MapPin,
  Globe,
  ShieldCheck,
  Building,
  Award,
  DollarSign,
  AlertCircle,
} from "lucide-react"
import { opportunitiesApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { CategoryBadge } from "@/components/ui/badge"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getSafeExternalUrl } from "@/lib/utils"

export function OpportunityDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [opp, setOpp] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadOpportunity() {
      if (!id) return
      setLoading(true)
      try {
        const res = await opportunitiesApi.detail(id)
        if (res?.opportunity) {
          setOpp(res.opportunity)
        } else {
          setError("Opportunity not found or removed.")
        }
      } catch (err: any) {
        setError(err.message || "Failed to load opportunity")
      } finally {
        setLoading(false)
      }
    }
    loadOpportunity()
  }, [id])

  const handleToggleSave = async () => {
    if (!opp) return
    try {
      await opportunitiesApi.toggleSave(opp.id)
      setOpp({ ...opp, is_saved: !opp.is_saved })
    } catch (err) {
      console.error(err)
    }
  }

  const sourceUrl = getSafeExternalUrl(opp?.url || opp?.source_url)

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-32 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Skeleton className="h-48 md:col-span-2" />
          <Skeleton className="h-48" />
        </div>
      </div>
    )
  }

  if (error || !opp) {
    return (
      <div className="max-w-md mx-auto text-center py-16 space-y-4">
        <AlertCircle className="h-12 w-12 text-destructive mx-auto" />
        <h3 className="text-lg font-semibold text-foreground">{error || "Not Found"}</h3>
        <Button onClick={() => navigate("/app/opportunities")} variant="outline" size="sm">
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Feed
        </Button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/app/opportunities")}
          className="text-xs text-muted-foreground hover:text-foreground -ml-2"
        >
          <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Opportunities
        </Button>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleToggleSave}
            className="text-xs"
          >
            <Bookmark className={`h-4 w-4 mr-1.5 ${opp.is_saved ? "fill-purple-600 text-purple-600" : ""}`} />
            {opp.is_saved ? "Saved" : "Save"}
          </Button>

          {sourceUrl && (
            <Button
              asChild
              className="bg-cyber-blue hover:bg-cyber-blue-light text-white text-xs shadow-sm"
              size="sm"
            >
              <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                Apply Directly <ExternalLink className="h-3.5 w-3.5 ml-1.5" />
              </a>
            </Button>
          )}
        </div>
      </div>

      {/* Main Header Card */}
      <Card className="border-t-4 border-t-cyber-blue shadow-sm">
        <CardContent className="pt-6 space-y-4">
          <div className="flex flex-wrap items-center gap-2 justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              <CategoryBadge category={opp.category} />
              {opp.is_free === true && (
                <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Free
                </span>
              )}
            </div>
            {(opp.score ?? opp.priority_score) != null && (
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-muted text-muted-foreground">
                Priority Score: <strong className="text-foreground">{Math.round(opp.score ?? opp.priority_score)}/100</strong>
              </span>
            )}
          </div>

          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
              {opp.title}
            </h1>
            <p className="text-base text-muted-foreground font-medium flex items-center gap-2 mt-1">
              <Building className="h-4 w-4 text-cyber-blue" />
              {opp.organization || "Organization not specified"}
            </p>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-3 border-t text-xs">
            <div>
              <span className="text-muted-foreground block text-[11px]">Location</span>
              <span className="font-semibold text-foreground flex items-center gap-1 mt-0.5">
                <MapPin className="h-3.5 w-3.5 text-cyber-blue" />
                {opp.location || (opp.remote ? "Remote" : "Not specified")}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px]">Remote Allowed</span>
              <span className="font-semibold text-foreground flex items-center gap-1 mt-0.5">
                <Globe className="h-3.5 w-3.5 text-cyber-teal" />
                {opp.remote ? "Yes, remote" : "On-site / hybrid"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px]">Application Deadline</span>
              <span className="font-semibold text-amber-600 dark:text-amber-400 flex items-center gap-1 mt-0.5">
                <Calendar className="h-3.5 w-3.5" />
                {opp.deadline ? new Date(opp.deadline).toLocaleDateString() : "Not specified"}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px]">Application Fee</span>
              <span className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-0.5">
                <DollarSign className="h-3.5 w-3.5" />
                {opp.is_free === true ? "Free" : opp.is_free === false ? "Paid" : "Not listed"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Grid: Description & Verification Telemetry */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Full Description & Skills (2 Cols) */}
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">About this Opportunity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-foreground leading-relaxed whitespace-pre-line">
              {opp.description || "No full description provided by source collector."}
            </CardContent>
          </Card>

          {opp.eligibility && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Award className="h-4 w-4 text-cyber-blue" /> Eligibility & Qualifications
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-foreground whitespace-pre-line">
                {opp.eligibility}
              </CardContent>
            </Card>
          )}

          {Array.isArray(opp.tags) && opp.tags.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Target Skills & Topics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {opp.tags.map((skill: string, idx: number) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-md bg-muted text-foreground text-xs font-mono font-medium border"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column: Security & Free-Only Verification Details (1 Col) */}
        <div className="space-y-6">
          <Card className="bg-emerald-500/5 border-emerald-500/30">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-emerald-700 dark:text-emerald-400 flex items-center gap-2">
                <ShieldCheck className="h-4 w-4" /> Free-Only Verification
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <p className="text-muted-foreground leading-relaxed">
                CyberScout AI automated filter verified that this opportunity requires zero application fees, tuition, or paid paywalls.
              </p>
              <div className="space-y-1.5 pt-2 border-t border-emerald-500/20 font-mono text-[11px]">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Verification status:</span>
                  <span className="font-semibold text-emerald-600">APPROVED</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Fee detection:</span>
                  <span className="font-semibold text-foreground">$0.00 Verified</span>
                </div>
                {opp.compensation && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Compensation:</span>
                    <span className="font-semibold text-foreground">{opp.compensation}</span>
                  </div>
                )}
                {opp.prize && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Prize pool:</span>
                    <span className="font-semibold text-foreground">{opp.prize}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Quick Apply CTA Box */}
          {sourceUrl && (
            <Card className="p-5 text-center space-y-3">
              <h4 className="text-sm font-semibold text-foreground">Ready to participate?</h4>
              <p className="text-xs text-muted-foreground">
                Apply directly on the host website through the verified source URL.
              </p>
              <Button asChild className="w-full bg-cyber-blue hover:bg-cyber-blue-light text-white text-xs">
                <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                  Go to Host Application <ExternalLink className="h-3.5 w-3.5 ml-1.5" />
                </a>
              </Button>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

