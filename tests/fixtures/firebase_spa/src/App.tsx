
import { signInAnonymously, getAuth } from 'firebase/auth';
import { getStorage, ref, uploadBytes } from 'firebase/storage';
import { getFirestore, collection, addDoc } from 'firebase/firestore';
export function Sidebar() {
  return (<nav>
    <a href="#terms">이용약관</a>
    <a href="#privacy">개인정보처리방침</a>
  </nav>);
}
export async function boot() {
  const auth = getAuth();
  await signInAnonymously(auth);
  const db = getFirestore();
  await addDoc(collection(db, 'messages'), { text: 'hi', uid: auth.currentUser?.uid });
  await addDoc(collection(db, 'logs'), { event: 'open', ttl: 90, expireAt: Date.now() + 90*86400000 });
  await addDoc(collection(db, 'teachers'), { email: 't@example.sen.go.kr', displayName: '교사' });
  const storage = getStorage();
  await uploadBytes(ref(storage, 'drawings/1.png'), new Blob());
}
