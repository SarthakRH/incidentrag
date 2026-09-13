{{- define "incidentrag.name" -}}incidentrag{{- end -}}
{{- define "incidentrag.fullname" -}}{{ .Release.Name }}-incidentrag{{- end -}}
{{- define "incidentrag.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "incidentrag.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
