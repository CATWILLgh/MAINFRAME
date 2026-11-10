import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';

const id=z.string().regex(/^[\w-]{1,200}$/),time=z.number().int().nonnegative();
// Strict allow-list: bodies, transcripts, errors, and output snapshots cannot be
// persisted accidentally. The native session log remains their only owner.
export const taskSchema=z.object({
  taskId:id,callerId:id,targetId:id,messageId:z.string().max(200),mode:z.enum(['followup','steer']),
  label:z.string().min(1).max(120).optional(),group:z.string().min(1).max(120).optional(),
  createdAt:time,updatedAt:time,expiresAt:time,deadline:time,
  afterSeq:z.number().int().min(-1).optional(),asOfSeq:z.number().int().min(-1).optional(),observedAt:time.optional(),
  delivery:z.enum(['prepared','accepted','unknown','not-sent']),
  observation:z.enum(['waiting','not-requested','idle','input-required','timeout','observation-error','error','stopped','cancelled']),
  notification:z.enum(['none','waiting','ready','claimed','delivered','unknown','cancelled']),
}).strict();
export const taskDomain=defineDomain({name:'mainframe_session_collaboration',version:1,layout:'single',tables:{tasks:domainTable(taskSchema)}});
export async function openTaskDomain(ctx) {return ctx.storageDomain.open(taskDomain);}
