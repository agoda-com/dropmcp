import styles from './ItemHero.module.css';

export default function ItemHero({ heroUrl, altText }: { heroUrl: string | null | undefined; altText: string }) {
  if (heroUrl) {
    return (
      <div className={styles.hero}>
        <img src={heroUrl} alt={altText} />
      </div>
    );
  }
  return <div className={styles.heroPlaceholder} />;
}
