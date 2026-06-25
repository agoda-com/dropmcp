export interface SubscriptionItem {
  item_type: 'skill' | 'prompt';
  item_name: string;
  created_at: string;
}

export async function subscribeItem(
  itemType: 'skill' | 'prompt',
  itemName: string,
): Promise<void> {
  const res = await fetch('/api/subscriptions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_type: itemType, item_name: itemName }),
  });
  if (!res.ok) {
    throw new Error(`Could not subscribe (${res.status}).`);
  }
}

export async function unsubscribeItem(
  itemType: 'skill' | 'prompt',
  itemName: string,
): Promise<void> {
  const res = await fetch(`/api/subscriptions/${itemType}/${itemName}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Could not unsubscribe (${res.status}).`);
  }
}

export async function subscribeGroup(group: string): Promise<void> {
  const res = await fetch(`/api/subscriptions/group/${encodeURIComponent(group)}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Could not subscribe to group (${res.status}).`);
  }
}

export async function unsubscribeGroup(group: string): Promise<void> {
  const res = await fetch(`/api/subscriptions/group/${encodeURIComponent(group)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Could not unsubscribe from group (${res.status}).`);
  }
}
