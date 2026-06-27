"""Train and save the Qualification Agent propensity model."""

from qualification_agent import MODEL_PATH, load_customer_index, train_model


def main():
    customers = load_customer_index()
    model = train_model(customers)
    with MODEL_PATH.open("wb") as file:
        import pickle

        pickle.dump(model, file)

    print(f"[OK] Trained propensity model on {len(customers)} customers -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
